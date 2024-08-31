"""
This is a module :)
"""

from datetime import datetime
from dataclasses import dataclass, field
import itertools
import logging
import os
import random
import socket
from pathlib import Path
import queue
import string
import struct
import threading
from typing import Any, Dict, Generator, Tuple

import atexit
from flask import Flask, Blueprint, jsonify, current_app, request, send_file
from werkzeug.serving import get_sockaddr, select_address_family
from werkzeug.serving import is_running_from_reloader
from werkzeug.utils import secure_filename

import requests
from zeroconf import ServiceInfo, Zeroconf

import cv2
import numpy as np

from host_app.wasm_utils.wasm import wasm_modules
from host_app.wasm_utils.wasm_api import MLModel, ModuleConfig
from host_app.wasm_utils.wasmtime import WasmtimeRuntime

from host_app.utils.configuration import get_device_description, get_wot_td
from host_app.utils.routes import endpoint_failed
from host_app.utils.deployment import Deployment, CallData
from host_app.utils.logger import get_logger


_MODULE_DIRECTORY = 'wasm-modules'
_PARAMS_FOLDER = 'wasm-params'
INSTANCE_PARAMS_FOLDER = None

OUTPUT_LENGTH_BYTES = 32 // 8
"""
Size in bytes of the length-type used to represent the size of the block of Wasm
memory containing output result of an executed WebAssembly function. e.g.
a block of 257 bytes can be enumerated with a 2 byte type such as a 16bit
integer but not with 1 byte.
"""

ALLOC_NAME = "alloc"
"""
Name used for the memory-allocation function that should be found in most every
WebAssembly module up for execution. Should have one parameter, which is the
length in bytes of the memory to allocate and returns beginning address of the
allocated block.
"""

@dataclass
class FetchFailures(Exception):
    """Raised when fetching modules or their attached files fails"""
    errors: list[requests.Response]

FLASK_APP = os.environ.get("FLASK_APP", __name__)

bp = Blueprint(os.environ["FLASK_APP"], os.environ["FLASK_APP"])

logger = logging.getLogger(FLASK_APP)

deployments = {}
"""
Mapping of deployment-IDs to instructions for forwarding function results to
other devices and calling their functions
"""


def request_counter() -> Generator[int, None, None]:
    """Returns a unique number for each request"""
    counter: int = 0
    while True:
        counter += 1
        yield counter

request_id_counters: Dict[str, Generator[int, None, None]] = {}


def path_to_string(result: Any) -> Any:
    """Converts all included Path objects to strings."""
    if isinstance(result, Path):
        return str(result)
    if isinstance(result, (list, tuple)):
        return [path_to_string(item) for item in result]
    if isinstance(result, dict):
        return {key: path_to_string(value) for key, value in result.items()}
    if isinstance(result, RequestEntry):
        result.result = path_to_string(result.result)
    return result


@dataclass
class RequestEntry():
    '''Describes a request of WebAssembly execution'''
    request_id: str = field(init=False)
    '''Unique identifier for this request'''
    deployment_id: str
    module_name: str
    function_name: str
    method: str
    request_args: Any
    request_files: Dict[str, str]
    work_queued_at: datetime
    result: Any = None
    success: bool = False

    def __post_init__(self):
        # TODO: Hash the ID (and include args and time as well) because in this
        # current way multiple same requests get overwritten.
        # - For now a simple request counter is used to distinguish requests for the same function
        request_id = f'{self.deployment_id}:{self.module_name}:{self.function_name}'
        if request_id not in request_id_counters:
            request_id_counters[request_id] = request_counter()
        self.request_id = f'{request_id}:{next(request_id_counters[request_id])}'

request_history = []
'''Log of all the requests handled by this supervisor'''

wasm_queue = queue.Queue()
'''Queue of work for asynchronous WebAssembly execution'''

def module_mount_path(module_name: str, filename: str | None = None) -> Path:
    """
    Return path for a file that will eventually be made available for a
    module
    """
    return Path(INSTANCE_PARAMS_FOLDER, module_name, filename if filename else "")

def do_wasm_work(entry: RequestEntry):
    '''
    Run a WebAssembly function and follow deployment instructions on what to
    do with its output.

    Return response of the possible call made or the raw result if chaining is
    not required.
    '''

    deployment = deployments[entry.deployment_id]

    logger.debug("Preparing Wasm module %r", entry.module_name)
    module, wasm_args = deployment.prepare_for_running(
        entry.module_name,
        entry.function_name,
        entry.request_args,
        entry.request_files
    )

    logger.debug("Running Wasm function %r", entry.function_name)
    raw_output = module.run_function(entry.function_name, wasm_args)
    logger.debug("... Result: %r", raw_output, extra={"raw_output": raw_output})

    # Do the next call, passing chain along and return immediately (i.e. the
    # answer to current request should not be such, that it significantly blocks
    # the whole chain).
    this_result, next_call = deployment.interpret_call_from(
        module.name, entry.function_name, raw_output
    )

    # Log the result of the execution of this one module function.
    # Execution result is the primitive output of the function, if any
    # Result URL is the URL where the a result file can be fetched from (if any)
    if this_result[0] is not None:
        get_logger(request).debug("Execution result: %s", this_result[0], extra={"request": entry})
    if this_result[1] is not None:
        ip, port = get_listening_address(current_app)
        get_logger(request).debug("Result url: http://%s:%s/module_results/%s/%s", ip, port, entry.module_name, this_result[1][0], extra={"request": entry})

    if not isinstance(next_call, CallData):
        # No sub-calls needed.
        return this_result

    headers = next_call.headers
    # NOTE: IIUC this matches how 'requests' documentation instructs to do for
    # multi-file uploads, so I'm guessing it closes the opened files once done.
    files = { name: open(module_mount_path(module.name, name), "rb") for name in next_call.files }

    get_logger(request).debug("Making sub-call from %r to %r", entry.module_name, next_call.url, extra={
        "request": entry,
        "next_call": next_call
    })

    sub_response = getattr(requests, next_call.method)(
        next_call.url,
        timeout=30,
        files=files,
        headers=headers,
    )

    return sub_response.json()["resultUrl"]

def make_history(entry: RequestEntry):
    '''Add entry to request history after executing its work'''
    try:
        entry.result = do_wasm_work(entry)
        entry.success = True
    except Exception as err:
        logger.error("Error running WebAssembly function %r", entry.function_name, exc_info=True, extra={
            "request": entry,
        })
        entry.result = str(err)
        entry.success = False

    request_history.append(entry)

    return entry

def wasm_worker():
    '''Constantly try dequeueing work for using WebAssembly modules'''
    while entry := wasm_queue.get():
        make_history(entry)
        wasm_queue.task_done()


def create_app(*args, **kwargs) -> Flask:
    '''
    Create a new Flask application.

    Registers the blueprint and initializes zeroconf.
    '''
    if is_running_from_reloader():
        raise RuntimeError("Running from reloader is not supported.")

    app = Flask(os.environ.get("FLASK_APP", __name__), *args, **kwargs)

    # Create instance directory if it does not exist.
    Path(app.instance_path).mkdir(exist_ok=True)

    app.config.update({
        'secret_key': 'dev',
        'MODULE_FOLDER': Path(app.instance_path, _MODULE_DIRECTORY),
        'PARAMS_FOLDER': Path(app.instance_path, _PARAMS_FOLDER),
    })

    # Set this in order to later access module params folder that Flask set up
    # on app creation.
    global INSTANCE_PARAMS_FOLDER
    INSTANCE_PARAMS_FOLDER = app.config['PARAMS_FOLDER']

    # Load config from instance/ -directory
    app.config.from_pyfile("config.py", silent=True)

    # Load config from environment variables
    app.config.from_prefixed_env("WASMIOT")

    # add sentry logging
    app.config.setdefault('SENTRY_DSN', os.environ.get('SENTRY_DSN'))

    from .logging.logger import init_app as init_logging  # pylint: disable=import-outside-toplevel
    init_logging(app, logger=logger)

    app.register_blueprint(bp)

    # Enable mDNS advertising.
    from .zc import WebthingZeroconf # pylint: disable=import-outside-toplevel
    WebthingZeroconf(app)

    # Start thread that handles the Wasm work queue.
    init_wasm_worker()

    return app


def init_wasm_worker():
    """
    Set up and start a thread that continuously dequeues given work for running
    Wasm.
    """
    def teardown_worker():
        """Signal the worker thread to stop and wait for it to finish."""
        wasm_queue.put(None)
        logger.debug("Waiting for the worker thread to finish...", end="")
        wasm_worker_thread.join()
        logger.debug("worker thread finished!")

    # Turn-on the worker thread.
    wasm_worker_thread = threading.Thread(target=wasm_worker, daemon=True)
    wasm_worker_thread.start()

    # Stop the worker thread before exiting.
    atexit.register(teardown_worker)


def get_listening_address(app: Flask) -> Tuple[str, int]:
    """
    Return the address Flask application is listening.

    TODO: Does not detect if listening on multiple addresses.
    """

    # Copied from flask/app.py and werkzeug.service how it determines address,
    # as serving address is not stored. By default flask uses request information
    # for this, but we can't rely on that.

    host = None
    port = None

    host = os.environ.get('SERVER_NAME', None)
    port = os.environ.get('FLASK_PORT', 5000)

    try:
        with app.app_context():
            # Try guessing from server name, default path for flask.
            server_name = app.config.get("SERVER_NAME")
            if server_name:
                host, _, port = server_name.partition(":")
            port = port or app.config.get("PORT") or 5000
    except RuntimeError as exc:
        logger.debug("Could not determine server name from flask app, as app context is not available")

    # Fallback
    if not host:
        # From https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib/28950776#28950776
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(("10.255.255.255", 1))
            host, *_ = s.getsockname()
        except Exception:
            host = "0.0.0.0"
        finally:
            s.close()

    address_family = select_address_family(host, port)
    server_address = get_sockaddr(host, int(port), address_family)
    if isinstance(server_address, str):
        # TODO: check if this case can happen and what should be the default port
        return server_address, 80
    return server_address

@bp.route('/.well-known/wasmiot-device-description')
def wasmiot_device_description():
    '''Return the device description containing host functions in JSON'''
    get_logger(request).info("Device description request served")
    return jsonify(get_device_description())

@bp.route('/.well-known/wot-thing-description')
def thingi_description():
    '''Return the Web of Things thing description in JSON'''
    return jsonify(get_wot_td())

@bp.route('/health')
def thingi_health():
    '''Return a report of the current health status of this thing'''
    get_logger(request).info("Health check done")
    return jsonify({
         "cpuUsage": random.random()
    })

@bp.route('/module_results/<module_name>/<filename>')
def get_module_result(module_name: str, filename: str):
    """
    Return the result file of a module execution.
    """
    return send_file(Path(INSTANCE_PARAMS_FOLDER, module_name, filename))

def results_route(request_id=None, full=False):
    '''
    Return the route where execution/request results can be read from.

    If full is True, return the full URL, otherwise just the path. This is so
    that routes can easily return URL for caller to read execution results.
    '''
    root = 'request-history'
    route = f'{root}/{request_id}' if request_id else root
    return f'{request.root_url}{route}' if full else route

@bp.route('/' + results_route())
@bp.route('/' + results_route('<request_id>'))
def request_history_list(request_id=None):
    '''Return a list of or a specific entry result from previous call'''
    if request_id is None:
        return jsonify(path_to_string(request_history))
    matching_requests = [x for x in request_history if x.request_id == request_id]
    if len(matching_requests) == 0:
        return endpoint_failed(request, 'no matching entry in history', 404)
    first_match = matching_requests[0]
    json_response = jsonify(path_to_string(first_match))
    json_response.status_code = 200 if first_match.success else 500
    return json_response

@bp.route('/<deployment_id>/modules/<module_name>/<function_name>', methods=["GET", "POST"])
@bp.route('/<deployment_id>/modules/<module_name>/<function_name>/<filename>', methods=["GET"])
def run_module_function(deployment_id, module_name, function_name, filename=None):
    '''
    Execute the function in WebAssembly module and act based on instructions
    attached to the deployment of this call/execution.
    '''

    if filename:
        # If a filename is passed, this route works merely for file serving.
        return send_file(module_mount_path(module_name, filename))

    if deployment_id not in deployments:
        return endpoint_failed(request, 'deployment does not exist', 404)

    if module_name not in deployments[deployment_id].modules:
        return endpoint_failed(request, f"module {module_name} not found for this deployment")

    # Write input data to filesystem.
    input_file_paths: Dict[str, str] = {}
    for param_name, input_data_file in request.files.items():
        input_file_path = os.path.join(
            current_app.config['PARAMS_FOLDER'],
            (
                input_data_file.name
                if input_data_file is not None and input_data_file.name is not None
                else ""
            )
        )
        input_data_file.save(input_file_path)
        input_file_paths[param_name] = str(Path(input_file_path))

    entry = RequestEntry(
        deployment_id,
        module_name,
        function_name,
        request.method,
        request.args,
        input_file_paths,
        datetime.now()
    )

    get_logger(request).info("Module run", extra={"request": entry})

    # Assume that the work wont take long and do it synchronously on GET.
    if request.method.lower() == 'get':
        make_history(entry)
    else:
        # Send data to worker thread to handle non-blockingly.
        wasm_queue.put(entry)
    
    # Return a link to this request's result (which could link further until
    # some useful value is found).
    return jsonify({ 'resultUrl': results_route(entry.request_id, full=True) })

@bp.route('/deploy/<deployment_id>', methods=['DELETE'])
def deployment_delete(deployment_id):
    '''
    Forget the given deployment.
    '''
    if deployment_id in deployments:
        del deployments[deployment_id]
        return jsonify({'status': 'success'})
    return endpoint_failed(request, 'deployment does not exist', 404)

@bp.route('/deploy', methods=['POST'])
def deployment_create():
    '''
    Request content-type needs to be 'application/json'
    - POST: Parses the deployment from request and enacts it.
    '''
    data = request.get_json(silent=True)
    if not data:
        get_logger(request).error('No deployment data found')
        return jsonify({'message': 'Non-existent or malformed deployment data'})
    modules = data['modules']

    if not modules:
        get_logger(request).error('No modules listed')
        return jsonify({'message': 'No modules listed'})

    try:
        module_configs = fetch_modules(modules)
    except FetchFailures as err:
        logger.error("Failed fetching modules", exc_info=True)
        return endpoint_failed(
            request,
            msg=f'{len(err.errors)} fetch failures',
            status_code=500,
            errors=err.errors
        )

    # Initialize __separate__ execution environments for each module for this
    # deployment, adding filepath roots for the modules' directories that they
    # are able to use. This way when file-access is granted via runtime, modules
    # will only access their own directories.
    modules_runtimes = {
        m.name: WasmtimeRuntime([str(module_mount_path(m.name))])
        for m in module_configs
    }

    deployments[data["deploymentId"]] = Deployment(
        data["deploymentId"],
        runtimes=modules_runtimes,
        _modules=module_configs,
        endpoints=data["endpoints"],
        _instructions=data["instructions"],
        _mounts=data["mounts"],
    )

    # If the fetching did not fail (that is, crash), return success.
    get_logger(request).info('Deployment created')
    return jsonify({'status': 'success'})

def fetch_modules(modules) -> list[ModuleConfig]:
    """
    Fetch listed Wasm-modules, save them and their details and return data that
    can be used to instantiate modules for execution later.
    :modules: list of structs of modules to download
    """
    configs = []
    for module in modules:
        # Make all the requests at once.
        res_bin = requests.get(module["urls"]["binary"], timeout=5)
        # Map the names of data files to their responses. The names are used to
        # save the files on disk for the module to use.
        res_others = {
            name: requests.get(url, timeout=5)
            for name, url in module.get("urls", {}).get("other", {}).items()
        }

        # Check that each request succeeded before continuing on.
        # Gather errors together.
        errors = []
        for res in itertools.chain([res_bin], res_others.values()):
            if not res.ok:
                errors.append(res)

        if errors:
            raise FetchFailures(errors)

        # "Request for module by name"
        module_path = os.path.join(current_app.config["MODULE_FOLDER"], module["name"])
        # Confirm that the module directory exists and create it if not TODO:
        # This would be better performed at startup.
        os.makedirs(current_app.config["MODULE_FOLDER"], exist_ok=True)
        with open(module_path, 'wb') as filepath:
            filepath.write(res_bin.content)

        # Add other listed files related to the module.
        data_files = {}
        for key, res_other in res_others.items():
            other_path = module_mount_path(module["name"], key)

            other_path.parent.mkdir(exist_ok=True, parents=True)
            with open(other_path, 'wb') as filepath:
                filepath.write(res_other.content)

            # Map the mount name to whatever path the actual file is at.
            data_files[key] = other_path

            # update the module configuration with the model path
            # TODO: Does having a "model path" attribute in the module
            # config have direct benefits over "generic" files list?
            # Something must point out the currently used model file for ML modules:
            # - a) either it is always assumed to be the first data file
            # - b) or there is a "special" attribute for the model
            # - c) alternatively there is some additional information about the data files,
            #   - type or description, that would indicate the model file
            # new_module_config.ml_model = MLModel(other_path)

        # Save downloaded module's details.
        new_module_config = ModuleConfig(
            id=module["id"],
            name=module["name"],
            path=module_path,
            data_files=data_files,
        )
        # combining options a) and b) from above:
        new_module_config.set_model_from_data_files()

        # Create the params directory for this module's files.
        new_module_mount_path = Path(module_mount_path(new_module_config.name))
        if not new_module_mount_path.exists():
            os.makedirs(new_module_mount_path, exist_ok=True)

        configs.append(new_module_config)

    return configs

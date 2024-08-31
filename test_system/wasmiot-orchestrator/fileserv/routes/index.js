/**
 * Inject dependencies into routes' global/module scope because Javascript
 * "classes" and the this-keyword are horrible.
 */

const device = require("./device");
const modules = require("./module");
const deployment = require("./deployment");
const execution = require("./execution");
const { init: initCoreServices } = require("./coreServices");
const supervisorLogs = require("./logs");


/* Set common dependencies between the API routes. */
async function init(routeDependencies) {
    device.setDatabase(routeDependencies.database);
    device.setDeviceDiscovery(routeDependencies.deviceDiscovery);

    modules.setDatabase(routeDependencies.database);

    deployment.setDatabase(routeDependencies.database);
    deployment.setOrchestrator(routeDependencies.orchestrator);

    execution.setDatabase(routeDependencies.database);
    execution.setOrchestrator(routeDependencies.orchestrator);

    let coreServicesRouter = await initCoreServices(routeDependencies);
    supervisorLogs.setDatabase(routeDependencies.database);

    return {
        device: device.router,
        modules: modules.router,
        deployment: deployment.router,
        execution: execution.router,
        coreServicesRouter,
        logs: supervisorLogs.router
    };
}

module.exports = { init };
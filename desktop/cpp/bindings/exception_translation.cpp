#include "api.hpp"

namespace neomath::bindings {

py::dict errorResult(const std::string& type, const std::string& code, const std::string& message) {
    py::dict error;
    error["type"] = type;
    error["code"] = code;
    error["message"] = message;
    error["details"] = py::dict();
    py::dict response;
    response["ok"] = false;
    response["error"] = std::move(error);
    py::dict metrics;
    metrics["durationMs"] = 0.0;
    metrics["cacheHits"] = 0;
    response["metrics"] = std::move(metrics);
    return response;
}

}  // namespace neomath::bindings

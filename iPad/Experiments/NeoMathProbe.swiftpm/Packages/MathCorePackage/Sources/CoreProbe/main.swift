import Foundation
import MathCoreBridge
let data = MathCoreBridge.trace("x*(x-1)=0\nx-1=0\nx=1")
let result = try JSONSerialization.jsonObject(with: data) as! [String: Any]
let steps = result["steps"] as! [[String: Any]]
precondition(steps[0]["solutions"] as? String == "{0, 1}")
precondition(steps[1]["status"] as? String == "root_fault")
precondition(steps[1]["witness"] as? String == "0")
print("PASS: SwiftPM calls original Objective-C++ and C++ core; solutions {0, 1}; lost-root witness 0")

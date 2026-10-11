#import <Foundation/Foundation.h>
#import "MathCoreBridge.h"
#include <cassert>
static NSDictionary *trace(NSString *source) {
    return [NSJSONSerialization JSONObjectWithData:[MathCoreBridge trace:source] options:0 error:nil];
}
int main() { @autoreleasepool {
    auto lost = trace(@"x(x-1)=0\nx-1=0\nx=1");
    assert([lost[@"steps"] count] == 3);
    assert([lost[@"steps"][0][@"solutions"] isEqual:@"{0, 1}"]);
    assert([lost[@"steps"][1][@"status"] isEqual:@"root_fault"]);
    assert([lost[@"steps"][1][@"witness"] isEqual:@"0"]);
    assert([lost[@"steps"][1][@"before"] isEqual:@"True"]);
    assert([lost[@"steps"][1][@"after"] isEqual:@"False"]);
    assert([lost[@"steps"][2][@"status"] isEqual:@"tainted"]);
    auto replay = trace(@"x(x-1)=0\nx-1=0\nx=0");
    assert([replay[@"cacheHits"] intValue] == 2);
    assert([replay[@"steps"][2][@"solutions"] isEqual:@"{0}"]);
    assert([replay[@"steps"][1][@"witness"] isEqual:@"0"]);
    auto good = trace(@"2x+3=7\n2x=4\nx=2");
    for (NSDictionary *step in good[@"steps"]) assert([step[@"status"] isEqual:@"valid"]);
    auto invalid = trace(@"x+=");
    assert([invalid[@"steps"][0][@"status"] isEqual:@"parse_error"]);
    auto unsupported = trace(@"x^3=2");
    assert(![unsupported[@"steps"][0][@"status"] isEqual:@"valid"]);
    auto changed = trace(@"x(x-1)=0\nx=0 or x=1");
    assert([changed[@"steps"][1][@"status"] isEqual:@"valid"]);
    auto data = [MathCoreBridge transform:@"2x+3=7" step:0 intent:@"solve"];
    NSDictionary *transformed = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    assert([transformed[@"applied"] boolValue]);
    assert([transformed[@"source"] length] > 0);
    NSDictionary *multiply = [NSJSONSerialization JSONObjectWithData:[MathCoreBridge transform:@"x=1" step:0 intent:@"multiply" argument:@"3"] options:0 error:nil];
    assert([multiply[@"applied"] boolValue]);
    assert([trace(multiply[@"source"])[@"steps"][0][@"solutions"] isEqual:@"{1}"]);
    NSDictionary *probe = [NSJSONSerialization JSONObjectWithData:[MathCoreBridge probe:@"x(x-1)=0\nx-1=0" value:@"0"] options:0 error:nil];
    assert([probe[@"steps"][0][@"after"] isEqual:@"True"]);
    assert([probe[@"steps"][1][@"after"] isEqual:@"False"]);
    NSDictionary *badProbe = [NSJSONSerialization JSONObjectWithData:[MathCoreBridge probe:@"x=1" value:@"1/0"] options:0 error:nil];
    assert(badProbe[@"error"] != nil);
    NSDictionary *completion = [NSJSONSerialization JSONObjectWithData:[MathCoreBridge completions:@"x-1=0" step:0] options:0 error:nil];
    assert([completion[@"items"] count] > 0);
    NSDictionary *solve = completion[@"items"][0];
    assert([solve[@"id"] isEqual:@"solve"] && [solve[@"available"] boolValue]);
    assert([solve[@"preview"] isEqual:@"x = 1"]);
    puts("Bridge tests passed: lost roots, exact witness, taint, equivalent steps, invalid syntax, unsupported degree, disjunction, transform.");
} }

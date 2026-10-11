#import <Foundation/Foundation.h>
NS_ASSUME_NONNULL_BEGIN
@interface MathCoreBridge : NSObject
+ (NSData *)trace:(NSString *)source;
+ (NSData *)completions:(NSString *)source step:(NSInteger)step;
+ (NSData *)probe:(NSString *)source value:(NSString *)value;
+ (NSData *)transform:(NSString *)source step:(NSInteger)step intent:(NSString *)intent;
+ (NSData *)transform:(NSString *)source step:(NSInteger)step intent:(NSString *)intent argument:(NSString *)argument;
@end
NS_ASSUME_NONNULL_END

//
//  Utils.h
//  VePlayerDemo
//
//  Created by Jihua Huang on 2020/7/14.
//  Copyright © 2020 ByteDance Ltd. All rights reserved.
//

#import <UIKit/UIKit.h>

@interface Utils : NSObject

/// 旋转设备
/// @param rotation 旋转度
+ (void)rotateDeviceToOrientation:(NSInteger)rotation;

+ (UIImage *)imageFromColor:(UIColor *)color;

+ (UIViewController *)getCurrentViewController;

@end

//
//  Utils.m
//  VePlayerDemo
//
//  Created by Jihua Huang on 2020/7/14.
//  Copyright © 2020 ByteDance Ltd. All rights reserved.
//

#import "Utils.h"

@implementation Utils

+ (void)rotateDeviceToOrientation:(NSInteger)rotation
{
    UIDeviceOrientation orientation = rotation == 270 ? UIDeviceOrientationLandscapeRight : UIDeviceOrientationPortrait;
    [[UIDevice currentDevice] setValue: @(UIDeviceOrientationUnknown) forKey: @"orientation"];
    [[UIDevice currentDevice] setValue: @(orientation) forKey: @"orientation"];
}

+ (UIImage *)imageFromColor:(UIColor *)color
{
    return [Utils imageFromColor:color withSize: CGSizeMake(10, 10)];
}

+ (UIImage *)imageFromColor:(UIColor *)color withSize:(CGSize)size
{
    CGSize imageSize = size;
    UIGraphicsBeginImageContextWithOptions(imageSize, 0, [UIScreen mainScreen].scale);
    [color set];
    UIRectFill(CGRectMake(0, 0, imageSize.width, imageSize.height));
    UIImage *image = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();
    return image;
}

+ (UIViewController *)getCurrentViewController
{
    UIViewController *rootViewController = ([UIApplication sharedApplication].delegate).window.rootViewController;
    if ([rootViewController isKindOfClass: [UITabBarController class]]) {
        UITabBarController *tabBarController = (UITabBarController *)rootViewController;
        UINavigationController *navigationController = tabBarController.selectedViewController;
        if ([navigationController isKindOfClass: [UINavigationController class]]) {
            return navigationController.topViewController;
        }
    }
    return nil;
}

@end

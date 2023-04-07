//
//  CustomViewController.m
//  VePlayerDemo
//
//  Created by changwuguo on 2022/11/16.
//  Copyright © 2022 ByteDance Ltd. All rights reserved.
//

#import "Utils.h"
#import "CustomViewController.h"

@implementation CustomViewController

- (void)setRotation:(NSInteger)rotation
{
    if (_rotation != rotation) {
        
        _rotation = rotation;
        
        if (@available(iOS 16, *)) {
            [self setNeedsUpdateOfSupportedInterfaceOrientations];
        } else {
            [Utils rotateDeviceToOrientation: rotation];
        }
    }
}

- (UIInterfaceOrientationMask)supportedInterfaceOrientations
{
    UIInterfaceOrientationMask mask = UIInterfaceOrientationMaskPortrait;
    if (self.rotation == 90 || self.rotation == 270) {
        mask = UIInterfaceOrientationMaskLandscapeRight;
    }
    return mask;
}

@end

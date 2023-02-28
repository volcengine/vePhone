//
//  SVProgressHUD+Category.m
//  VePlayerDemo
//
//  Created by changwuguo on 2022/11/18.
//  Copyright © 2022 ByteDance Ltd. All rights reserved.
//

#import "SVProgressHUD+Category.h"
#import <objc/runtime.h>

@implementation SVProgressHUD (Category)

+ (void)load
{
    Method bogusMethod = class_getInstanceMethod([SVProgressHUD class], NSSelectorFromString(@"bogusInitWithFrame:"));
    Method method = class_getInstanceMethod([SVProgressHUD class], @selector(initWithFrame:));
    method_exchangeImplementations(bogusMethod, method);
}

- (instancetype)bogusInitWithFrame:(CGRect)frame
{
    [self bogusInitWithFrame: frame];
    self.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    return self;
}

@end

//
//  VePhoneDisplayViewController.h
//  VePhonePublicDemo
//
//  Created by changwuguo on 2021/09/06.
//  Copyright © 2021 ByteDance Ltd. All rights reserved.
//

#import <UIKit/UIKit.h>

@interface VeCloudPhoneConfigObject : NSObject

@property (nonatomic, copy) NSString *ak;
@property (nonatomic, copy) NSString *sk;
@property (nonatomic, copy) NSString *token;
@property (nonatomic, copy) NSString *podId;
@property (nonatomic, copy) NSString *userId;
@property (nonatomic, copy) NSString *productId;
@property (nonatomic, assign) NSInteger streamType;
@property (nonatomic, assign) NSInteger rotationMode;
@property (nonatomic, assign) NSInteger autoRecycleTime;
@property (nonatomic, assign) NSInteger localKeyboardEnable;

@end

@interface VePhoneDisplayViewController : UIViewController

@property (nonatomic, strong) VeCloudPhoneConfigObject *configObj;

@end

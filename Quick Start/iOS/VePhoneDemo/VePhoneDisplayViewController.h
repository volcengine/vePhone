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
@property (nonatomic, assign) NSInteger rotation;

@end

@interface VePhoneDisplayViewController : UIViewController

@property (nonatomic, strong) VeCloudPhoneConfigObject *configObj;

@end

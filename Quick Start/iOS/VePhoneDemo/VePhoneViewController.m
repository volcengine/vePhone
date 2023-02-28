//
//  VePhoneViewController.m
//  Demo
//
//  Created by changwuguo on 2021/09/06.
//  Copyright © 2021 ByteDance Ltd. All rights reserved.
//

#import "Utils.h"
#import <Toast/Toast.h>
#import <VePhone/VePhone.h>
#import "VePhoneViewController.h"
#import "VePhoneDisplayViewController.h"

@interface VePhoneViewController ()

@property (weak, nonatomic) IBOutlet UILabel *versionLabel;
@property (weak, nonatomic) IBOutlet UITextField *akTextField;
@property (weak, nonatomic) IBOutlet UITextField *skTextField;
@property (weak, nonatomic) IBOutlet UITextField *tokenTextField;
@property (weak, nonatomic) IBOutlet UITextField *userIdTextField;
@property (weak, nonatomic) IBOutlet UITextField *productIdTextField;
@property (weak, nonatomic) IBOutlet UITextField *rotationTextField;

@end

@implementation VePhoneViewController

- (void)viewDidLoad
{
    [super viewDidLoad];

    self.navigationItem.title = @"云手机演示";
    
    self.akTextField.text = @"====ak====";
    self.skTextField.text = @"====sk====";
    self.tokenTextField.text = @"====token====";
    
    self.rotationTextField.text = @"0";
    self.userIdTextField.text = @"====userId====";
    self.productIdTextField.text = @"====productId====";
    // 版本号
    self.versionLabel.text = [NSString stringWithFormat: @"VePhoneSDK版本: V%@\nDeviceId: %@", [VePhoneManager currentVersion], [VePhoneManager currentDeviceId]];
}

- (void)viewWillAppear:(BOOL)animated
{
    [super viewWillAppear: animated];

    [Utils rotateDeviceToOrientation: UIDeviceOrientationPortrait];
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event
{
    [self.view endEditing: YES];
}

- (IBAction)tappedStartPhoneButton:(UIButton *)sender
{
    if (self.akTextField.text.length == 0 || self.skTextField.text.length == 0 || self.tokenTextField.text.length == 0 || self.userIdTextField.text.length == 0 || self.productIdTextField.text.length == 0) {
        NSString *str = @"";
        if (self.akTextField.text.length == 0) {
            str = @"Ak不能为空";
        } else if (self.skTextField.text.length == 0) {
            str = @"Sk不能为空";
        } else if (self.tokenTextField.text.length == 0) {
            str = @"Token不能为空";
        } else if (self.userIdTextField.text.length == 0) {
            str = @"UserId不能为空";
        } else if (self.productIdTextField.text.length == 0) {
            str = @"ProductId不能为空";
        }
        [self.view makeToast: str duration: 2.0f position: CSToastPositionCenter];
        return;
    }
    // 显示控制器
    VePhoneDisplayViewController *phoneDisplayVc = [[VePhoneDisplayViewController alloc] init];
    VeCloudPhoneConfigObject *obj = [VeCloudPhoneConfigObject new];
    obj.ak = self.akTextField.text;
    obj.sk = self.skTextField.text;
    obj.token = self.tokenTextField.text;
    obj.userId = self.userIdTextField.text;
    obj.productId = self.productIdTextField.text;
    obj.rotation = self.rotationTextField.text.integerValue;
    phoneDisplayVc.configObj = obj;
    [self.navigationController pushViewController: phoneDisplayVc animated: YES];
}

@end


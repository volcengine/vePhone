//
//  VePhoneDisplayViewController.m
//  VePhonePublicDemo
//
//  Created by changwuguo on 2021/09/06.
//  Copyright © 2021 ByteDance Ltd. All rights reserved.
//

#import "Masonry.h"
#import <VePhone/VePhone.h>
#import <SVProgressHUD/SVProgressHUD.h>
#import "VePhoneDisplayViewController.h"

@implementation VeCloudPhoneConfigObject

@end

@interface VePhoneDisplayViewController () <VePhoneManagerDelegate>

@property (nonatomic, assign) NSInteger rotation;
@property (nonatomic, strong) UIView *containerView;

@end

@implementation VePhoneDisplayViewController

- (void)viewDidLoad
{
    [super viewDidLoad];
    
    self.hidesBottomBarWhenPushed = YES;
    self.view.backgroundColor = [UIColor blackColor];
    
    [self configUI];
    
    self.rotation = self.configObj.rotation;
    
    [SVProgressHUD showWithStatus: @"正在启动..."];
    // 初始化云手机实例
    [VePhoneManager sharedManagerWithContainerView: self.containerView delegate: self];
    // 配置信息
    VePhoneConfigObject *configObj = [VePhoneConfigObject new];
    configObj.ak = self.configObj.ak;
    configObj.sk = self.configObj.sk;
    configObj.token = self.configObj.token;
    configObj.userId = self.configObj.userId;
    configObj.productId = self.configObj.productId;
    // 启动
    [[VePhoneManager sharedInstance] startWithConfig: configObj];
}

- (void)viewWillAppear:(BOOL)animated
{
    [super viewWillAppear: animated];

    [self.navigationController setNavigationBarHidden: YES animated: YES];
    self.navigationController.interactivePopGestureRecognizer.enabled = NO;
}

- (void)viewWillDisappear:(BOOL)animated
{
    [super viewWillDisappear: animated];

    [self.navigationController setNavigationBarHidden: NO animated: YES];
    self.navigationController.interactivePopGestureRecognizer.enabled = YES;
}

- (UIStatusBarStyle)preferredStatusBarStyle
{
    return UIStatusBarStyleLightContent;
}

- (void)configUI
{
    // 容器视图
    self.containerView = ({
        UIView *containerView = [[UIView alloc] init];
        [self.view addSubview: containerView];
        [containerView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.left.top.right.bottom.mas_equalTo(0);
        }];
        containerView;
    });
    
    // 退出
    UIButton *exitBtn = [UIButton buttonWithType: UIButtonTypeCustom];
    exitBtn.layer.borderWidth = 1.0f;
    exitBtn.layer.borderColor = [UIColor whiteColor].CGColor;
    exitBtn.layer.cornerRadius = 5.0f;
    exitBtn.titleLabel.font = [UIFont systemFontOfSize: 14.0f];
    [exitBtn setTitle: @"关闭" forState: UIControlStateNormal];
    [exitBtn setTitleColor: [UIColor whiteColor] forState: UIControlStateNormal];
    [exitBtn addTarget: self action: @selector(tappedExitButton:) forControlEvents: UIControlEventTouchUpInside];
    [self.view addSubview: exitBtn];
    [exitBtn mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(self.view).offset(50.0f);
        make.left.mas_equalTo(self.view).offset(30.0f);
        make.size.mas_equalTo(CGSizeMake(50.0f, 30.0f));
    }];
}

#pragma mark - VePhoneManagerDelegate

- (void)phoneManager:(VePhoneManager *)manager startSucceedResult:(NSInteger)streamProfileId reservedId:(NSString *)reservedId extra:(NSDictionary *)extra
{
    [SVProgressHUD dismiss];
}

- (void)phoneManager:(VePhoneManager *)manager changedDeviceRotation:(NSInteger)rotation
{
    self.rotation = rotation;
}

- (void)phoneManager:(VePhoneManager *)manager operationDelay:(NSInteger)delayTime
{
    // NSLog(@"delayTime = %f", delayTime);
}

- (void)phoneManager:(VePhoneManager *)manager onError:(VePhoneErrorCode)errorCode
{
    [SVProgressHUD dismiss];
    
    NSLog(@"errorCode = %ld", errorCode);
}

#pragma mark - button action

- (void)tappedExitButton:(UIButton *)btn
{
    [SVProgressHUD dismiss];
    [[VePhoneManager sharedInstance] stop];
    [self.navigationController popViewControllerAnimated: YES];
}

#pragma mark - setter

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

- (BOOL)shouldAutorotate
{
    return YES;
}

- (UIInterfaceOrientationMask)supportedInterfaceOrientations
{
    UIInterfaceOrientationMask mask = UIInterfaceOrientationMaskPortrait;
    if (self.rotation == 270) {
        mask = UIInterfaceOrientationMaskLandscapeRight;
    }
    return mask;
}

- (void)dealloc
{
    NSLog(@"--- VePhoneDisplayViewController Dealloc ---");
}


@end

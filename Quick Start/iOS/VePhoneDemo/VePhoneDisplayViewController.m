//
//  VePhoneDisplayViewController.m
//  VePhonePublicDemo
//
//  Created by changwuguo on 2021/09/06.
//  Copyright © 2021 ByteDance Ltd. All rights reserved.
//

#import "Masonry.h"
#import <SVProgressHUD/SVProgressHUD.h>
#import "VePhoneDisplayViewController.h"

#import "Utils.h"
#import "Constants.h"
#import <Toast/Toast.h>
#import "UserInfoManager.h"
#import "AudioCaptureTool.h"
#import "VideoCaptureTool.h"
#import "VeCloudPhonePreview.h"
#import "CustomViewController.h"
#import <VePhone/VePhone.h>
#import <AVFoundation/AVFoundation.h>
#import <SVProgressHUD/SVProgressHUD.h>
#import <CommonCrypto/CommonDigest.h>
#import "UIView+Draggable.h"

@implementation VeCloudPhoneConfigObject

@end

@interface VePhoneDisplayViewController () <VePhoneManagerDelegate, UIImagePickerControllerDelegate, UINavigationControllerDelegate>

@property (nonatomic, assign) BOOL isNavShow;
@property (nonatomic, assign) NSInteger rotation;
@property (nonatomic, strong) UIView *containerView;
@property (nonatomic, strong) UIView *localVideoView;
@property (nonatomic, strong) UILabel *timelylogLabel;
@property (nonatomic, strong) UIScrollView *scrollView;
@property (nonatomic, copy) NSString *operationDelayTime;
// 音频采集
@property (nonatomic, strong) AudioCaptureConfig *audioCaptureConfig;
@property (nonatomic, strong) AudioCaptureTool *audioCapture;
// 视频采集
@property (nonatomic, strong) VideoCaptureConfig *videoCaptureConfig;
@property (nonatomic, strong) VideoCaptureTool *videoCapture;

@end

@implementation VePhoneDisplayViewController

- (void)viewDidLoad
{
    [super viewDidLoad];
    
    [self configSubView];
    [self setupAudioSession];
    
    self.rotation = 0;
    [SVProgressHUD showWithStatus: @"正在启动..."];
    [VePhoneManager sharedInstance].delegate = self;
    [VePhoneManager sharedInstance].containerView = self.containerView;
    // 相关开关
    [VePhoneManager sharedInstance].gyroEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingGyroEnabled];
    [VePhoneManager sharedInstance].vibratorEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingVibratorEnabled];
    [VePhoneManager sharedInstance].oritationEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingOrientationEnabled];
    [VePhoneManager sharedInstance].locationEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingLocationRequestEnabled];
    [VePhoneManager sharedInstance].magnetometerEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingMagnetometerEnabled];
    [VePhoneManager sharedInstance].accelerometerEnable = [[NSUserDefaults standardUserDefaults] boolForKey: keySettingAccelerometerEnabled];
    // 附加信息
    [[VePhoneManager sharedInstance] setExtraParameters: @{
        @"key_code_bypass": @(NO),
    }];
    // 配置信息
    VePhoneConfigObject *configObj = [VePhoneConfigObject new];
    configObj.ak = self.configObj.ak;
    configObj.sk = self.configObj.sk;
    configObj.token = self.configObj.token;
    configObj.podId = self.configObj.podId;
    configObj.userId = self.configObj.userId;
    configObj.productId = self.configObj.productId;
    configObj.rotationMode = self.configObj.rotationMode;
    configObj.autoRecycleTime = self.configObj.autoRecycleTime;
    configObj.localKeyboardEnable = self.configObj.localKeyboardEnable;
    // configObj.remoteWindowSize = CGSizeMake(0, 0);
    // configObj.videoRenderMode = VeBaseVideoRenderModeFit;
    // 订阅类型
    [VePhoneManager sharedInstance].streamType = self.configObj.streamType;
    // 启动
    [[VePhoneManager sharedInstance] startWithConfig: configObj];
    
    [[NSNotificationCenter defaultCenter] addObserver: self
                                             selector: @selector(receiveAppWillTerminateNotification:)
                                                 name: UIApplicationWillTerminateNotification
                                               object: nil];
    [[NSNotificationCenter defaultCenter] addObserver: self
                                             selector: @selector(receiveAppDidEnterBackgroundNotification:)
                                                 name: UIApplicationDidEnterBackgroundNotification
                                               object: nil];
    [[NSNotificationCenter defaultCenter] addObserver: self
                                             selector: @selector(receiveAppWillEnterForegroundNotification:)
                                                 name: UIApplicationWillEnterForegroundNotification
                                               object: nil];
}

- (void)viewWillAppear:(BOOL)animated
{
    [super viewWillAppear: animated];

    [self.navigationController setNavigationBarHidden: YES animated: YES];
}

- (void)viewWillDisappear:(BOOL)animated
{
    [super viewWillDisappear: animated];

    [self.navigationController setNavigationBarHidden: NO animated: YES];
}

- (void)viewDidLayoutSubviews
{
    [super viewDidLayoutSubviews];
    
    UIButton *menuBtn = [self.view viewWithTag: 999];
    if (menuBtn.draggingType == DraggingTypeDisabled) {
        menuBtn.draggingType = DraggingTypePullOver;
    }
}

- (UIStatusBarStyle)preferredStatusBarStyle
{
    return UIStatusBarStyleLightContent;
}

- (void)configSubView
{
    // 画布
    self.containerView = ({
        UIView *containerView = [[UIView alloc] init];
        containerView.backgroundColor = [UIColor blackColor];
        [self.view addSubview: containerView];
        [containerView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.edges.insets(UIEdgeInsetsMake(0, 0, 0, 0));
        }];
        containerView;
    });
    
    // 本地视频采集视图
    self.localVideoView = ({
        UIView *localVideoView = [[UIView alloc] init];
        localVideoView.hidden = YES;
        localVideoView.backgroundColor = [UIColor blackColor];
        [self.view addSubview: localVideoView];
        [localVideoView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.right.mas_equalTo(self.view).offset(-10.0f);
            make.size.mas_equalTo(CGSizeMake(150.0f, 200.0f));
            make.top.mas_equalTo(self.view.mas_top).offset(44);
        }];
        localVideoView;
    });
    
    // 实时日志
    self.timelylogLabel = ({
        UILabel *label = [[UILabel alloc] init];
        label.userInteractionEnabled = NO;
        label.textColor = [UIColor greenColor];
        label.textAlignment = NSTextAlignmentCenter;
        label.font = [UIFont systemFontOfSize: 11.0f];
        label.backgroundColor = [UIColor grayColor];
        label.layer.masksToBounds = YES;
        label.layer.cornerRadius = 6.0f;
        label.adjustsFontSizeToFitWidth = YES;
        [self.view addSubview: label];
        [label mas_makeConstraints:^(MASConstraintMaker *make) {
            make.centerX.mas_equalTo(self.view);
            make.bottom.mas_equalTo(self.view).offset(-34);
        }];
        label;
    });
    
    // 菜单
    UIButton *menuBtn = [UIButton buttonWithType: UIButtonTypeCustom];
    menuBtn.tag = 999;
    menuBtn.layer.cornerRadius = 14.0f;
    menuBtn.backgroundColor = [UIColor redColor];
    menuBtn.titleLabel.font = [UIFont systemFontOfSize: 9.0f];
    [menuBtn setTitle: @"Menu" forState: UIControlStateNormal];
    [menuBtn setTitleColor: [UIColor yellowColor] forState: UIControlStateNormal];
    [menuBtn addTarget: self action: @selector(tappedButton:) forControlEvents: UIControlEventTouchUpInside];
    [self.view addSubview: menuBtn];
    [menuBtn mas_makeConstraints:^(MASConstraintMaker *make) {
        make.right.mas_equalTo(self.view);
        make.size.mas_equalTo(CGSizeMake(28, 28));
        make.bottom.mas_equalTo(self.view).offset(-100);
    }];
    
    self.scrollView = ({
        UIScrollView *scrollView = [[UIScrollView alloc] init];
        scrollView.hidden = YES;
        scrollView.showsVerticalScrollIndicator = NO;
        [self.view addSubview: scrollView];
        [scrollView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.width.mas_equalTo(170);
            make.left.mas_equalTo(self.view).offset(10.0f);
            make.top.mas_equalTo(self.view).offset(44);
            make.bottom.mas_equalTo(self.view).offset(-34);
        }];
        scrollView;
    });
    
    UIView *btnView = [[UIView alloc] init];
    [self.scrollView addSubview: btnView];
    [btnView mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.left.right.bottom.mas_equalTo(self.scrollView);
        make.width.mas_equalTo(self.scrollView);
    }];
    
    UIButton *button0 = [self createButton: @"退出"];
    button0.tag = 100;
    button0.backgroundColor = [UIColor redColor];
    [button0 setTitleColor: [UIColor yellowColor] forState: UIControlStateNormal];
    [btnView addSubview: button0];
    [button0 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(btnView);
        make.left.mas_equalTo(btnView);
        make.size.mas_equalTo(CGSizeMake(80, 40));
    }];
    
    UIButton *button1 = [self createButton: @"摄像头类型"];
    button1.tag = 101;
    [btnView addSubview: button1];
    [button1 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button0);
        make.top.mas_equalTo(button0);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button2 = [self createButton: @"开启镜像"];
    button2.tag = 102;
    button2.selected = YES;
    [btnView addSubview: button2];
    [button2 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button0);
        make.left.mas_equalTo(button0);
        make.top.mas_equalTo(button0.mas_bottom).offset(10);
    }];
    
    UIButton *button3 = [self createButton: @"发送消息(无回执)"];
    button3.tag = 103;
    [btnView addSubview: button3];
    [button3 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button2);
        make.top.mas_equalTo(button2);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button4 = [self createButton: @"发送消息(超时3秒)"];
    button4.tag = 104;
    [btnView addSubview: button4];
    [button4 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button2);
        make.left.mas_equalTo(button2);
        make.top.mas_equalTo(button2.mas_bottom).offset(10);
    }];
    
    UIButton *button5 = [self createButton: @"发送消息(uid，无回执)"];
    button5.tag = 105;
    [btnView addSubview: button5];
    [button5 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button4);
        make.top.mas_equalTo(button4);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button6 = [self createButton: @"发送消息(uid，超时3秒)"];
    button6.tag = 106;
    [btnView addSubview: button6];
    [button6 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button4);
        make.left.mas_equalTo(button4);
        make.top.mas_equalTo(button4.mas_bottom).offset(10);
    }];
    
    UIButton *button7 = [self createButton: @"截图"];
    button7.tag = 107;
    [btnView addSubview: button7];
    [button7 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button6);
        make.top.mas_equalTo(button6);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button8 = [self createButton: @"键盘事件"];
    button8.tag = 108;
    [btnView addSubview: button8];
    [button8 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button6);
        make.left.mas_equalTo(button6);
        make.top.mas_equalTo(button6.mas_bottom).offset(10);
    }];
    
    UIButton *button9 = [self createButton: @"焦点应用包名"];
    button9.tag = 109;
    [btnView addSubview: button9];
    [button9 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button8);
        make.top.mas_equalTo(button8);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button10 = [self createButton: @"清晰度切换"];
    button10.tag = 110;
    [btnView addSubview: button10];
    [button10 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button8);
        make.left.mas_equalTo(button8);
        make.top.mas_equalTo(button8.mas_bottom).offset(10);
    }];
    
    UIButton *button11 = [self createButton: @"设置无操作回收时长"];
    button11.tag = 111;
    [btnView addSubview: button11];
    [button11 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button10);
        make.top.mas_equalTo(button10);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button12 = [self createButton: @"获取无操作回收时长"];
    button12.tag = 112;
    [btnView addSubview: button12];
    [button12 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button10);
        make.left.mas_equalTo(button10);
        make.top.mas_equalTo(button10.mas_bottom).offset(10);
    }];
    
    UIButton *button13 = [self createButton: @"设置后台保活时长"];
    button13.tag = 113;
    [btnView addSubview: button13];
    [button13 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button12);
        make.top.mas_equalTo(button12);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button14 = [self createButton: @"切换前后台"];
    button14.tag = 114;
    [btnView addSubview: button14];
    [button14 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button12);
        make.left.mas_equalTo(button12);
        make.top.mas_equalTo(button12.mas_bottom).offset(10);
    }];
    
    UIButton *button15 = [self createButton: self.configObj.streamType == VeBaseStreamTypeVideo ? @"静音打开" : @"静音关闭"];
    button15.tag = 115;
    [btnView addSubview: button15];
    button15.selected = self.configObj.streamType == VeBaseStreamTypeVideo;
    [button15 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button14);
        make.top.mas_equalTo(button14);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button16 = [self createButton: self.configObj.streamType == VeBaseStreamTypeAudio ? @"视频暂停" : @"视频播放"];
    button16.tag = 116;
    [btnView addSubview: button16];
    button16.selected = self.configObj.streamType == VeBaseStreamTypeAudio;
    [button16 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button14);
        make.left.mas_equalTo(button14);
        make.top.mas_equalTo(button14.mas_bottom).offset(10);
    }];
    
    UIButton *button17 = [self createButton: @"采集视图隐藏"];
    button17.tag = 117;
    [btnView addSubview: button17];
    [button17 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button16);
        make.top.mas_equalTo(button16);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button18 = [self createButton: @"音频播放设备"];
    button18.tag = 118;
    [btnView addSubview: button18];
    [button18 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button16);
        make.left.mas_equalTo(button16);
        make.top.mas_equalTo(button16.mas_bottom).offset(10);
    }];
    
    UIButton *button19 = [self createButton: @"剪切板"];
    button19.tag = 119;
    [btnView addSubview: button19];
    [button19 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button18);
        make.top.mas_equalTo(button18);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button20 = [self createButton: @"开始录屏"];
    button20.tag = 120;
    [btnView addSubview: button20];
    [button20 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button18);
        make.left.mas_equalTo(button18);
        make.top.mas_equalTo(button18.mas_bottom).offset(10);
    }];
    
    UIButton *button21 = [self createButton: @"推送文件"];
    button21.tag = 121;
    [btnView addSubview: button21];
    [button21 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button20);
        make.top.mas_equalTo(button20);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button22 = [self createButton: @"拉取文件"];
    button22.tag = 122;
    [btnView addSubview: button22];
    [button22 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button20);
        make.left.mas_equalTo(button20);
        make.top.mas_equalTo(button20.mas_bottom).offset(10);
    }];
    
    UIButton *button23 = [self createButton: @"切换远端应用到前台"];
    button23.tag = 123;
    [btnView addSubview: button23];
    [button23 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button22);
        make.top.mas_equalTo(button22);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button24 = [self createButton: @"获取后台APP列表"];
    button24.tag = 124;
    [btnView addSubview: button24];
    [button24 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button22);
        make.left.mas_equalTo(button22);
        make.top.mas_equalTo(button22.mas_bottom).offset(10);
    }];
    
    UIButton *button25 = [self createButton: @"设置导航条"];
    button25.tag = 125;
    [btnView addSubview: button25];
    [button25 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button24);
        make.top.mas_equalTo(button24);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button26 = [self createButton: @"获取导航条状态"];
    button26.tag = 126;
    [btnView addSubview: button26];
    [button26 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button24);
        make.left.mas_equalTo(button24);
        make.top.mas_equalTo(button24.mas_bottom).offset(10);
    }];
    
    UIButton *button27 = [self createButton: @"调高音量"];
    button27.tag = 127;
    [btnView addSubview: button27];
    [button27 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button26);
        make.top.mas_equalTo(button26);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button28 = [self createButton: @"降低音量"];
    button28.tag = 128;
    [btnView addSubview: button28];
    [button28 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button26);
        make.left.mas_equalTo(button26);
        make.top.mas_equalTo(button26.mas_bottom).offset(10);
    }];
    
    UIButton *button29 = [self createButton: @"渲染模式"];
    button29.tag = 129;
    [btnView addSubview: button29];
    [button29 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button28);
        make.top.mas_equalTo(button28);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button30 = [self createButton: @"查询指定用户控制权"];
    button30.tag = 130;
    [btnView addSubview: button30];
    [button30 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button28);
        make.left.mas_equalTo(button28);
        make.top.mas_equalTo(button28.mas_bottom).offset(10);
    }];
    
    UIButton *button31 = [self createButton: @"查询所有用户控制权"];
    button31.tag = 131;
    [btnView addSubview: button31];
    [button31 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button30);
        make.top.mas_equalTo(button30);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button32 = [self createButton: @"设置指定用户控制权"];
    button32.tag = 132;
    [btnView addSubview: button32];
    [button32 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button30);
        make.left.mas_equalTo(button30);
        make.top.mas_equalTo(button30.mas_bottom).offset(10);
    }];
    
    UIButton *button33 = [self createButton: @"开启触控事件"];
    button33.tag = 133;
    [btnView addSubview: button33];
    [button33 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button32);
        make.top.mas_equalTo(button32);
        make.right.mas_equalTo(btnView);
        make.bottom.mas_equalTo(btnView);
    }];
}

#pragma mark - VePhoneManagerDelegate

- (void)firstRemoteAudioFrameArrivedFromPhoneManager:(VePhoneManager *)manager
{
    if (manager.streamType == VeBaseStreamTypeAudio) {
        [SVProgressHUD dismiss];
    }
}

- (void)phoneManager:(VePhoneManager *)manager startSucceedResult:(NSInteger)streamProfileId reservedId:(NSString *)reservedId extra:(NSDictionary *)extra
{
    [SVProgressHUD dismiss];
    [manager setLocalVideoCanvas: self.localVideoView];
}

- (void)phoneManager:(VePhoneManager *)manager changedDeviceRotation:(NSInteger)rotation
{
    if (self.configObj.rotationMode != VeBaseRotationModePortrait) {
        self.rotation = rotation;
    }
}

- (void)phoneManager:(VePhoneManager *)manager operationDelay:(NSInteger)delayTime
{
    self.operationDelayTime = [NSString stringWithFormat: @"%ld", (long)delayTime];
}

- (void)phoneManager:(VePhoneManager *)manager onLocalStreamStats:(VeBaseLocalStreamStats *)stats
{
    // NSLog(@"local stream stats: %@", [stats description]);
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteStreamStats:(VeBaseRemoteStreamStats *)stats
{
    dispatch_async(dispatch_get_main_queue(), ^{
        self.timelylogLabel.text = [NSString stringWithFormat: @"delay: %@ms rtt: %ldms loss: %.2f%% bit: %ldkbps fps: %ldfps",
                                    self.operationDelayTime ?: @"0", (long)stats.videoRtt, stats.audioLossRate + stats.videoLossRate, stats.receivedVideoKBitrate, (long)stats.rendererOutputFrameRate];
    });
}

- (void)phoneManager:(VePhoneManager *)manager onNetworkQuality:(VeBaseNetworkQuality)quality
{
    switch (quality) {
        case VeBaseNetworkQualityGood:
        {
             // NSLog(@"--- 网络情况良好 Quality:%li ---", quality);
        }
            break;
        case VeBaseNetworkQualityBad:
        {
             // NSLog(@"--- 网络情况较差 Quality:%li ---", quality);
        }
            break;
        case VeBaseNetworkQualityVeryBad:
        {
             // NSLog(@"--- 网络情况糟糕 Quality:%li ---", quality);
        }
            break;
        case VeBaseNetworkQualityDown:
        {
             // NSLog(@"--- 网络不可用 Quality:%li ---", quality);
        }
            break;
        default:
            break;
    }
}

- (void)startAudioCaptureRequestFromPhoneManager:(VePhoneManager *)manager
{
    if (manager.audioSourceType == VeBaseMediaSourceTypeInternal) {
        [SVProgressHUD showWithStatus: @"正在启动麦克风..."];
        [manager startAudioStream];
    } else {
        [self.audioCapture start];
    }
}

- (void)stopAudioCaptureRequestFromPhoneManager:(VePhoneManager *)manager
{
    if (manager.audioSourceType == VeBaseMediaSourceTypeInternal) {
        [manager stopAudioStream];
    } else {
        [self.audioCapture stop];
    }
}

- (void)phoneManager:(VePhoneManager *)manager onAudioCaptureDeviceState:(VeBaseMediaDeviceState)state deviceError:(VeBaseMediaDeviceError)error
{
    [SVProgressHUD dismiss];
    if (error == VeBaseMediaDeviceErrorDeviceNoPermission) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.view makeToast: @"错误，没有麦克风权限"
                        duration: 2.0f
                        position: CSToastPositionCenter];
        });
    }
}

- (void)phoneManager:(VePhoneManager *)manager startVideoCaptureRequest:(VeBaseCameraId)cameraId
{
    if (manager.videoSourceType == VeBaseMediaSourceTypeInternal) {
        [manager startVideoStream: cameraId];
    } else {
        [self.videoCapture start];
        self.videoCapture.previewLayer.hidden = NO;
        [self.videoCapture changeDevicePosition: cameraId == VeBaseCameraIdFront ? AVCaptureDevicePositionFront : AVCaptureDevicePositionBack];
    }
}

- (void)stopVideoCaptureRequestFromPhoneManager:(VePhoneManager *)manager
{
    if (manager.videoSourceType == VeBaseMediaSourceTypeInternal) {
        [manager stopVideoStream];
    } else {
        self.videoCapture.previewLayer.hidden = YES;
        [self.videoCapture stop];
    }
}

- (void)firstLocalVideoFrameCapturedFromPhoneManager:(VePhoneManager *)manager
{
    NSLog(@"本地视频采集：首帧到达");
}

- (void)phoneManager:(VePhoneManager *)manager onVideoCaptureDeviceState:(VeBaseMediaDeviceState)state deviceError:(VeBaseMediaDeviceError)error
{
    if (error == VeBaseMediaDeviceErrorDeviceNoPermission) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.view makeToast: @"错误，没有摄像头权限"
                        duration: 2.0f
                        position: CSToastPositionCenter];
        });
    }
}

- (void)phoneManager:(VePhoneManager *)manager onScreenShot:(NSInteger)code savePath:(NSString *)path downloadUrl:(NSString *)url
{
    NSString *toast = [NSString stringWithFormat: @"云手机截图结果：%@，SavePath = %@, DownloadUrl = %@", code == 0 ? @"成功" : @"失败", path, url];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    CGFloat width = [UIScreen mainScreen].bounds.size.width / 2.;
    CGFloat height = width * 1920.0f / 1080.0f;
    CGRect rect = CGRectMake(width - 10, 50, width, height);
    VeCloudPhonePreview *preview = [[VeCloudPhonePreview alloc] initWithFrame:rect];
    [self.view addSubview: preview];
    [preview loadImageWithUrl: url];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager switchVideoStreamProfile:(BOOL)result fromIndex:(NSInteger)index1 toIndex:(NSInteger)index2 targetParams:(NSDictionary *)paramsDict
{
    NSString *toast = [NSString stringWithFormat: @"清晰度切换：%@，fromIndex = %@, toIndex = %@", result ? @"成功" : @"失败", @(index1), @(index2)];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager receivedClipBoardMessage:(NSArray *)dataArray
{
    NSString *toast = [NSString stringWithFormat: @"远端剪贴板回调：%@", dataArray];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteMessageOnline:(NSString *)channel_uid
{
    NSString *toast = [NSString stringWithFormat: @"Message Channel Online = %@", channel_uid];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteMessageOffline:(NSString *)channel_uid
{
    NSString *toast = [NSString stringWithFormat: @"Message Channel Offline = %@", channel_uid];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onReceiveMessage:(VeBaseChannelMessage *)message
{
    NSString *toast = [NSString stringWithFormat: @"Receive Message = %@", [message description]];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onSendMessageResult:(BOOL)result messageId:(NSString *)mid
{
    NSString *toast = [NSString stringWithFormat: @"Send Message Result = %@，MessageId = %@", result ? @"成功" : @"失败", mid];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager getFocusedWindowApp:(NSInteger)code packageName:(NSString *)packageName
{
    NSString *toast = [NSString stringWithFormat: @"FocusedWindowApp：code = %ld，pakName = %@", code, packageName];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager setAutoRecycleTimeCallback:(NSInteger)code time:(NSInteger)time
{
    NSString *toast = [NSString stringWithFormat: @"设置无操作回收时长：%@，time = %ld", code == 0 ? @"成功" : @"失败", time];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager getAutoRecycleTimeCallback:(NSInteger)code time:(NSInteger)time
{
    NSString *toast = [NSString stringWithFormat: @"获取无操作回收时长：%@，time = %ld", code == 0 ? @"成功" : @"失败", time];
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onRevicedRemoteAppList:(NSArray *)appList
{
    NSLog(@"RevicedRemoteAppList = %@", appList);
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteAppSwitchedForeground:(NSString *)packageName switchType:(VeBaseRemoteAppSwitchedType)switchType
{
    NSLog(@"RemoteAppSwitchedForeground = %@ switchType = %@", packageName, switchType == VeBaseRemoteAppSwitchedTypeAutoSucceed ? @"自动切换" : @"手动切换");
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteAppSwitchedBackground:(NSString *)packageName switchType:(VeBaseRemoteAppSwitchedType)switchType
{
    NSLog(@"RemoteAppSwitchedBackground = %@ switchType = %@", packageName, switchType == VeBaseRemoteAppSwitchedTypeAutoSucceed ? @"自动切换" : @"手动切换");
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteAppSwitchedFailedWithCode:(VePhoneWarningCode)warningCode errorMsg:(NSString *)errorMsg
{
    NSLog(@"RemoteAppSwitchedFailed = %ld errorMsg = %@", warningCode, errorMsg);
}

- (void)phoneManager:(VePhoneManager *)manager status:(VeBaseRecordingStatus)status savePath:(NSString *)savePath msg:(NSString *)msg downloadUrl:(NSString *)url
{
    NSLog(@"status: %li  savePath: %@ downloadUrl: %@ msg: %@", status, savePath, url, msg);
}

- (void)phoneManager:(VePhoneManager *)manager onNavBarStatus:(NSInteger)status reason:(NSInteger)reason
{
    self.isNavShow = status;
    [self.view makeToast: [NSString stringWithFormat: @"导航栏--%@", status == 0 ? @"隐藏" : @"显示"]
                duration: 2.0f
                position: CSToastPositionCenter];
}

- (void)phoneManager:(VePhoneManager *)manager onUserJoin:(NSString *)uid
{
    dispatch_async(dispatch_get_main_queue(), ^{
        [self.view makeToast: [NSString stringWithFormat: @"Pod 远端用户Uid:%@加入房间", uid] duration: 2.0f position: CSToastPositionBottom];
    });
}

- (void)phoneManager:(VePhoneManager *)manager onUserLeave:(NSString *)uid
{
    dispatch_async(dispatch_get_main_queue(), ^{
        [self.view makeToast: [NSString stringWithFormat: @"Pod 远端用户Uid:%@离开房间", uid] duration: 2.0f position: CSToastPositionBottom];
    });
}

- (void)phoneManager:(VePhoneManager *)manager onEnableControlResult:(NSInteger)code state:(VePhoneControlState *)state message:(NSString *)msg
{
    NSString *toast = [NSString stringWithFormat: @"配置指定用户操控权：%@，state = %@, msg：%@", code == 0 ? @"成功" : @"失败", [state description], msg];
    [self.view makeToast: toast duration: 2.0f position: CSToastPositionBottom];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onControlStateChanged:(VePhoneControlState *)state
{
    NSString *toast = [NSString stringWithFormat: @"房间内操控权变更：state = %@", [state description]];
    [self.view makeToast: toast duration: 2.0f position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onHasControlResult:(NSInteger)code state:(VePhoneControlState *)state message:(NSString *)msg
{
    NSString *toast = [NSString stringWithFormat: @"查询房间内指定用户操控权信息：%@，state = %@, msg：%@", code == 0 ? @"成功" : @"失败", [state description], msg];
    [self.view makeToast: toast duration: 2.0f position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onAllControlsResult:(NSInteger)code list:(NSArray<VePhoneControlState *> *)states message:(NSString *)msg
{
    NSMutableString *str = [NSMutableString string];
    for (VePhoneControlState *state in states) {
        [str appendFormat: @"%@; ", [state description]];
    }
    if ([str hasSuffix: @"; "]) {
        [str deleteCharactersInRange: NSMakeRange(str.length - 2, 2)];
    }
    NSString *toast = [NSString stringWithFormat: @"查询房间内所有用户操控权信息：%@，states = %@, msg：%@", code == 0 ? @"成功" : @"失败", str, msg];
    [self.view makeToast: toast duration: 2.0f position: CSToastPositionCenter];
    NSLog(@"%@", toast);
}

- (void)phoneManager:(VePhoneManager *)manager onTouchEvent:(NSArray<VeBaseTouchEventItem *> *)touchArray
{
    NSLog(@"touchArray = %@", touchArray);
}

- (void)phoneManager:(VePhoneManager *)manager networkTypeChangedToType:(VeBaseNetworkType)networkType
{
    NSString *str = @"";
    switch (networkType) {
        case VeBaseNetworkTypeUnknown:
            str = @"当前网络类型：未知";
            break;
        case VeBaseNetworkTypeDisconnected:
            str = @"当前网络已断开";
            break;
        case VeBaseNetworkTypeLAN:
            str = @"当前网络类型：LAN局域网";
            break;
        case VeBaseNetworkTypeWIFI:
            str = @"当前网络类型：WIFI";
            break;
        case VeBaseNetworkTypeMobile2G:
            str = @"当前网络类型：2G";
            break;
        case VeBaseNetworkTypeMobile3G:
            str = @"当前网络类型：3G";
            break;
        case VeBaseNetworkTypeMobile4G:
            str = @"当前网络类型：4G";
            break;
        case VeBaseNetworkTypeMobile5G:
            str = @"当前网络类型：5G";
            break;
    }
    if (str.length > 0) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.view makeToast: str
                        duration: 2.0f
                        position: CSToastPositionBottom];
        });
    }
}

- (void)phoneManager:(VePhoneManager *)manager onPodExit:(VePhoneErrorCode)errCode
{
    dispatch_async(dispatch_get_main_queue(), ^{
        [SVProgressHUD dismiss];
        NSString *toast = @"";
        if (errCode == ERROR_REMOTE_ABNORMAL_EXIT) {
            toast = @"40000 云端服务异常退出";
        } else if (errCode == ERROR_REMOTE_CRASH) {
            toast = @"40001 云端服务崩溃";
        } else if (errCode == ERROR_STREAM_STOPPED_AUTO_RECYCLE) {
            toast = @"40004 长期未操作，云端服务自动断开";
        } else if (errCode == ERROR_REMOTE_STOPPED_API) {
            toast = @"40006 服务端主动停止云端服务";
        } else if (errCode == ERROR_POD_STOPPED_BACKGROUND_TIMEOUT) {
            toast = @"40008 云端服务后台超时";
        } else if (errCode == ERROR_POD_EXIT_GENERAL) {
            toast = @"40009 云端游戏退出";
        }
        if (toast.length > 0) {
            [self.view makeToast: toast
                        duration: 2.0f
                        position: CSToastPositionCenter];
        }
    });
}

- (void)phoneManager:(VePhoneManager *)manager onMessageChannleError:(VePhoneErrorCode)errCode
{
    dispatch_async(dispatch_get_main_queue(), ^{
        NSString *toast = @"";
        if (errCode == ERROR_MESSAGE_GENERAL) {
            toast = @"50000 消息通道通用错误";
        } else if (errCode == ERROR_MESSAGE_NOT_CONNECTED) {
            toast = @"50001 消息通道无连接";
        } else if (errCode == ERROR_MESSAGE_FAILED_TO_PARSE_MSG) {
            toast = @"50002 消息通道数据解析失败";
        } else if (errCode == ERROR_MESSAGE_CHANNEL_UID_ILLEGAL) {
            toast = @"50003 消息通道ID非法";
        } else if (errCode == ERROR_MESSAGE_OVER_SIZED) {
            toast = @"50007 消息体超过60kb";
        } else if (errCode == ERROR_MESSAGE_TIMEOUT_ILLEGAL) {
            toast = @"50009 消息发送超时时间非法";
        }
        if (toast.length > 0) {
            [self.view makeToast: toast
                        duration: 2.0f
                        position: CSToastPositionCenter];
        }
    });
}


- (void)phoneManager:(VePhoneManager *)manager onWarning:(VePhoneWarningCode)warnCode
{
    dispatch_async(dispatch_get_main_queue(), ^{
        NSString *toast = @"";
        if (warnCode == WARNING_START_NO_STOP_BEFORE) {
            toast = @"10010 启动游戏失败，原因：连续调用了两次Start之间没有调用 Stop";
        } else if (warnCode == WARNING_START_INVALID_AUTO_RECYCLE_TIME) {
            toast = @"10019 设置无操作回收服务时长非法";
        } else if (warnCode == WARNING_SDK_LACK_OF_LOCATION_PERMISSION) {
            toast = @"30007 无定位权限";
        } else if (warnCode == WARNING_LOCAL_ALREADY_SET_BACKGROUND) {
            toast = @"40037 用户重复调用切换后台接口";
        } else if (warnCode == WARNING_LOCAL_ALREADY_SET_FOREGROUND) {
            toast = @"40038 用户重复调用切换前台接口";
        }
        if (toast.length > 0) {
            [self.view makeToast: toast
                        duration: 2.0f
                        position: CSToastPositionCenter];
        }
    });
}

- (void)phoneManager:(VePhoneManager *)manager onError:(VePhoneErrorCode)errCode
{
    dispatch_async(dispatch_get_main_queue(), ^{
        [SVProgressHUD dismiss];
        NSString *toast = @"";
        if (errCode == ERROR_START_GENERAL) {
            toast = @"10000 未知错误";
        } else if (errCode == ERROR_START_AUTHENTICATION_KEY_FAILED) {
            toast = @"10009 鉴权 Token 过期";
        } else if (errCode == ERROR_START_CONNECTION_ENDED) {
            toast = @"10011 启动云手机失败，原因：在调用start接口后，start成功回调触发前，游戏被停止";
        } else if (errCode == ERROR_START_INVALID_LOCAL_TIME) {
            toast = @"10027 本地时间导致token过期";
        } else if (errCode == ERROR_START_PRODUCT_NOT_EXIST) {
            toast = @"11001 业务不存在";
        } else if (errCode == ERROR_START_APPLICATION_NOT_EXIST) {
            toast = @"11002 应用不存在";
        } else if (errCode == ERROR_START_PHONE_CONFIGURATION_CODE_NOT_EXIST) {
            toast = @"11003 请求套餐错误";
        } else if (errCode == ERROR_START_POD_NOT_EXIST) {
            toast = @"11004 实例不存在";
        } else if (errCode == ERROR_REQUEST_PARAMETER_BINDING_ERROR) {
            toast = @"11005 请求参数错误";
        } else if (errCode == ERROR_INVALID_REQUEST_PARAMETER) {
            toast = @"11006 请求参数错误";
        } else if (errCode == ERROR_BUSINESS_ID_ERROR) {
            toast = @"11007 业务错误";
        } else if (errCode == ERROR_ACCOUNT_ID_INIT_ERROR) {
            toast = @"11008 账户错误";
        } else if (errCode == ERROR_ACCOUNT_ID_NOT_FOUND) {
            toast = @"11009 账户错误";
        } else if (errCode == ERROR_USER_IS_INVALID) {
            toast = @"11010 User错误";
        } else if (errCode == ERROR_GENERIC_INSTANCE_ERROR) {
            toast = @"11011 设备异常";
        } else if (errCode == ERROR_INSTANCE_OFFLINE) {
            toast = @"11012 设备离线";
        } else if (errCode == ERROR_UNIVERSAL_STARTUP_FAILED) {
            toast = @"11013 通用启动失败（云原生）";
        } else if (errCode == ERROR_INTERNAL_POD_START_FAILED) {
            toast = @"11014 Pod 启动失败";
        } else if (errCode == ERROR_INTERNAL_POD_MUTE_FAILED) {
            toast = @"11015 启动内部错误";
        } else if (errCode == ERROR_INTERNAL_CONFIG_FAILED) {
            toast = @"11016 启动内部错误";
        } else if (errCode == ERROR_ACCOUNTID_MISMATCH) {
            toast = @"11019 火山账号不匹配";
        } else if (errCode == ERROR_POD_NOT_READY) {
            toast = @"11014 Pod 未就绪";
        } else if (errCode == ERROR_DOWN_STREAM_UNKNOWN_ERROR) {
            toast = @"11021 服务下游未知错误";
        } else if (errCode == ERROR_STREAM_GENERAL) {
            toast = @"20000 游戏串流连接错误";
        } else if (errCode == ERROR_STREAM_CHANGE_CLARITY_ID_NOT_IN_START_STATE) {
            toast = @"20002 切换清晰度失败，原因：在非播放状态下";
        } else if (errCode == ERROR_SDK_GENERAL) {
            toast = @"30000 SDK 通用错误";
        } else if (errCode == ERROR_SDK_INIT_FAILED) {
            toast = @"30001 初始化 SDK 实例化失败";
        } else if (errCode == ERROR_SDK_CONFIG_OR_AUTH_PARAMETER_EMPTY) {
            toast = @"30002 启动参数为空";
        } else if (errCode == ERROR_SDK_INVALID_VIDEO_CONTAINER) {
            toast = @"30008 画布尺寸无效";
        } else if (errCode == ERROR_INIT_ACCOUNT_ID_ILLEGAL) {
            toast = @"30009 火山账户ID非法";
        } else if (errCode == ERROR_NET_REQUEST_ERROR) {
            toast = @"60001 网络请求失败";
        } else if (errCode == ERROR_HTTP_REQUEST_ERROR) {
            toast = @"60002 网络请求失败";
        }
        if (toast.length > 0) {
            [self.view makeToast: toast
                        duration: 2.0f
                        position: CSToastPositionCenter];
        }
    });
}

#pragma mark - Utils

- (UIButton *)createButton:(NSString *)title
{
    UIButton *button = [UIButton buttonWithType: UIButtonTypeCustom];
    button.layer.cornerRadius = 3.0f;
    button.titleLabel.adjustsFontSizeToFitWidth = YES;
    button.backgroundColor = [UIColor systemBlueColor];
    button.titleLabel.font = [UIFont systemFontOfSize: 13.0f];
    [button setTitle: title forState: UIControlStateNormal];
    [button setTitleColor: [UIColor whiteColor] forState: UIControlStateNormal];
    [button addTarget: self action: @selector(tappedButton:) forControlEvents: UIControlEventTouchUpInside];
    return button;
}

#pragma mark - button action

- (void)tappedButton:(UIButton *)btn
{
    if (btn.tag == 999) { // Menu
        btn.selected = !btn.selected;
        self.scrollView.hidden = !btn.selected;
    } else if (btn.tag == 100) { // 退出
        [SVProgressHUD dismiss];
        [[VePhoneManager sharedInstance] stop];
        [self.navigationController popViewControllerAnimated: YES];
    } else if (btn.tag == 101) {
        btn.selected = !btn.selected;
        if ([VePhoneManager sharedInstance].audioSourceType == VeBaseMediaSourceTypeInternal) {
            [[VePhoneManager sharedInstance] switchCamera: btn.selected ? VeBaseCameraIdFront : VeBaseCameraIdBack];
        } else {
            [self.videoCapture changeDevicePosition: btn.selected ? AVCaptureDevicePositionFront : AVCaptureDevicePositionBack];
        }
        [btn setTitle: btn.selected ? @"前置摄像头" : @"后置摄像头" forState: UIControlStateNormal];
        [self.view makeToast: btn.currentTitle
                    duration: 2.0f
                    position: CSToastPositionCenter];
    } else if (btn.tag == 102) {
        btn.selected = !btn.selected;
        [[VePhoneManager sharedInstance] setLocalVideoMirrorType: btn.selected ? VeBaseMirrorTypeRender : VeBaseMirrorTypeNone];
        [btn setTitle: btn.selected ? @"开启镜像" : @"关闭镜像" forState: UIControlStateNormal];
        [self.view makeToast: btn.currentTitle
                    duration: 2.0f
                    position: CSToastPositionCenter];
    } else if (btn.tag == 103) {
        NSString *payload = @"ByteDance Is The Best Internet Company";
        VeBaseChannelMessage *msg = [[VePhoneManager sharedInstance] sendMessage: payload];
        NSLog(@"send no ack msg: %@", [msg description]);
    } else if (btn.tag == 104) {
        NSString *payload = @"ByteDance‘s CEO is LiangRuBo";
        VeBaseChannelMessage *msg = [[VePhoneManager sharedInstance] sendMessage: payload timeout: 3000];
        NSLog(@"send timeout msg: %@", [msg description]);
    } else if (btn.tag == 105) {
        for (int i = 1; i <= 5; i++) {
            NSString *payload = @"ByteDance Is The Best Internet Company";
            NSString *channel_uid = [NSString stringWithFormat: @"com.bytedance.vemessagechannelprj.prj%d", i];
            VeBaseChannelMessage *msg = [[VePhoneManager sharedInstance] sendMessage: payload channel: channel_uid];
            NSLog(@"send no ack channel msg: %@", [msg description]);
        }
    } else if (btn.tag == 106) {
        for (int i = 1; i <= 5; i++) {
            NSString *payload = @"ByteDance‘s CEO is LiangRuBo";
            NSString *channel_uid = [NSString stringWithFormat: @"com.bytedance.vemessagechannelprj.prj%d", i];
            VeBaseChannelMessage *msg = [[VePhoneManager sharedInstance] sendMessage: payload timeout: 3000 channel: channel_uid];
            NSLog(@"send timeout channel msg: %@", [msg description]);
        }
    } else if (btn.tag == 107) {
        [self setCustomViewController: @"截图保存到Pod" hintText: @"0：不保存 1：保存" tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                [[VePhoneManager sharedInstance] screenShot: [tf.text integerValue]];
            }
        }];
    } else if (btn.tag == 108) {
        [self setCustomViewController: @"请输入KeyCode" hintText: nil tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                if ([[VePhoneManager sharedInstance] sendKeyEvent: [tf.text integerValue]] == -1) {
                    [SVProgressHUD showInfoWithStatus: @"KeyCode无效"];
                }
            }
        }];
    } else if (btn.tag == 109) {
        [[VePhoneManager sharedInstance] getFocusedWindowApp];
    } else if (btn.tag == 110) {
        [self setCustomViewController: @"设置清晰度档位" hintText: nil tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                [[VePhoneManager sharedInstance] switchVideoStreamProfile: tf.text.integerValue];
            }
        }];
    } else if (btn.tag == 111) {
        __weak typeof(self)weakSelf = self;
        [self setCustomViewController: @"设置无操作回收时长" hintText: nil tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                if ([[VePhoneManager sharedInstance] setAutoRecycleTime: [tf.text integerValue]] == -2) {
                    [weakSelf.view makeToast: @"设置的时间小于等于0，非法！"
                                    duration: 2.0f
                                    position: CSToastPositionCenter];
                }
            }
        }];
    } else if (btn.tag == 112) {
        [[VePhoneManager sharedInstance] getAutoRecycleTime];
    } else if (btn.tag == 113) {
        __weak typeof(self)weakSelf = self;
        [self setCustomViewController: @"设置后台保活时长" hintText: nil tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                if ([[VePhoneManager sharedInstance] setIdleTime: [tf.text integerValue]] == -2) {
                    [weakSelf.view makeToast: @"设置的时间小于等于0，非法！"
                                    duration: 2.0f
                                    position: CSToastPositionCenter];
                }
            }
        }];
    } else if (btn.tag == 114) {
        btn.selected = !btn.selected;
        [[VePhoneManager sharedInstance] switchBackground: btn.selected];
        [btn setTitle: btn.selected ? @"切换到后台" : @"切换到前台" forState: UIControlStateNormal];
        [self.view makeToast: btn.currentTitle
                    duration: 2.0f
                    position: CSToastPositionCenter];
        
    } else if (btn.tag == 115) {
        btn.selected = !btn.selected;
        [[VePhoneManager sharedInstance] muteAudio: btn.selected];
        [btn setTitle: btn.selected ? @"静音打开" : @"静音关闭" forState: UIControlStateNormal];
        [self.view makeToast: btn.currentTitle
                    duration: 2.0f
                    position: CSToastPositionCenter];
        
    } else if (btn.tag == 116) {
        btn.selected = !btn.selected;
        [[VePhoneManager sharedInstance] muteVideo: btn.selected];
        [btn setTitle: btn.selected ? @"视频暂停" : @"视频播放" forState: UIControlStateNormal];
        [self.view makeToast: btn.currentTitle
                    duration: 2.0f
                    position: CSToastPositionCenter];
        
    } else if (btn.tag == 117) {
        btn.selected = !btn.selected;
        self.localVideoView.hidden = !btn.selected;
        [btn setTitle: btn.selected ? @"采集视图显示" : @"采集视图隐藏" forState: UIControlStateNormal];
    } else if (btn.tag == 118) {
        CustomViewController *alert = [CustomViewController alertControllerWithTitle: @"音频播放设备" message:nil preferredStyle: UIAlertControllerStyleActionSheet];
        alert.rotation = self.rotation;
        NSArray *subTitleArray = @[@"有线耳机", @"听筒", @"扬声器", @"蓝牙耳机", @"USB设备"];
        for (int i = 1; i < 6; i++) {
            UIAlertAction *action = [UIAlertAction actionWithTitle: subTitleArray[i - 1] style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
                [[VePhoneManager sharedInstance] setAudioPlaybackDevice: i];
            }];
            [alert addAction: action];
        }
        UIAlertAction *action5 = [UIAlertAction actionWithTitle: @"取消" style:UIAlertActionStyleCancel handler: nil];
        [alert addAction: action5];
        [self presentViewController: alert animated: NO completion: nil];
    } else if (btn.tag == 119) {
        NSArray<NSString *> *strings = [UIPasteboard generalPasteboard].strings;
        if (strings.count > 0) {
            [[VePhoneManager sharedInstance] sendClipBoardMessage: strings];
        } else {
            [SVProgressHUD showInfoWithStatus: @"剪切板数据为空"];
        }
    } else if (btn.tag == 120) {
        //开始录屏
        __weak typeof(self) weakSelf = self;
        [self setCustomViewController: @"录屏保存到Pod" hintText: @"0：不保存 1：保存" tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                btn.selected = !btn.selected;
                [weakSelf.view makeToast: btn.currentTitle
                                duration: 2.0f
                                position: CSToastPositionCenter];
                if (btn.isSelected) {
                    [[VePhoneManager sharedInstance] startRecording: 10 saveOnPod: [tf.text integerValue]];
                } else {
                    [[VePhoneManager sharedInstance] stopRecording];
                }
                [btn setTitle: btn.selected ? @"停止录屏" : @"开始录屏" forState: UIControlStateNormal];
            }
        }];
    } else if (btn.tag == 121) {
        UIImagePickerController *imagePicker = [[UIImagePickerController alloc] init];
        imagePicker.delegate = self;
        imagePicker.allowsEditing = YES;
        imagePicker.sourceType = UIImagePickerControllerSourceTypePhotoLibrary;
        imagePicker.modalPresentationStyle = UIModalPresentationFullScreen;
        [self presentViewController:imagePicker animated:YES completion:nil];
    } else if (btn.tag == 122) {
        NSArray *paths = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES);
        NSString *path = [paths objectAtIndex:0];
        CustomViewController *alert = [CustomViewController alertControllerWithTitle:nil message:@"输入拉取路径" preferredStyle:UIAlertControllerStyleAlert];
        alert.rotation = self.rotation;
        __block NSString *target;
        __block UITextField *tf1;
        __block UITextField *tf2;
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            textField.placeholder = @"请输入拉取的文件名";
            textField.text = @"test.png";
            tf1 = textField;
        }];
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            textField.placeholder = @"请输入存储路径，不输入则默认存储至Document下";
            textField.text = path;
            tf2 = textField;
        }];
        VeFile *file = [VeFile new];
        file.name = tf1.text ?: @"test.png";
        file.podFilePath = @"/sdcard/Download/";
        UIAlertAction *leftAction = [UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
            target = tf2.text;
            [[VePhoneManager sharedInstance] startPullFile:file target:target onStart:^(VeFile *file) {
                NSLog(@"拉取文件开始-------%@\n", file);
            } onProgress:^(VeFile *file, NSInteger progress) {
                [SVProgressHUD showProgress:progress / 100.0 status:[NSString stringWithFormat:@"文件拉取中(%ld)%%", progress]];
                NSLog(@"拉取文件进度-------%ld\n", progress);
            } onComplete:^(VeFile *file, NSString *url) {
                [SVProgressHUD dismiss];
                NSLog(@"拉取文件完成-------%@\n", url);
            } onCancel:^(VeFile *file) {
                [SVProgressHUD dismiss];
                NSLog(@"取消拉取文件-------%@\n", file);
            } onError:^(VeFile *file, VePhoneErrorCode err) {
                [SVProgressHUD dismiss];
                NSLog(@"拉取文件错误-------%@----errorCode = %ld\n", file, err);
            }];
        }];
        [alert addAction:leftAction];
        dispatch_async(dispatch_get_main_queue(), ^{
            [self presentViewController:alert animated:NO completion:nil];
        });
    } else if (btn.tag == 123) {
        [self setCustomViewController: @"切换远端App到前台" hintText: @"请输入packageName" tappedSureBlock:^(UITextField *tf) {
            if (tf.text.length != 0) {
                [[VePhoneManager sharedInstance] setRemoteAppForeground: tf.text];
            }
        }];
    } else if (btn.tag == 124) {
        [[VePhoneManager sharedInstance] getRemoteBackgroundAppList];
    } else if (btn.tag == 125) {
        [[VePhoneManager sharedInstance] setNavBarStatus: !self.isNavShow];
    } else if (btn.tag == 126) {
        [[VePhoneManager sharedInstance] getNavBarStatus];
    } else if (btn.tag == 127) {
        [[VePhoneManager sharedInstance] volumeUp];
    } else if (btn.tag == 128) {
        [[VePhoneManager sharedInstance] volumeDown];
    } else if (btn.tag == 129) {
        [self setCustomViewController: @"设置渲染模式" hintText: @"0: Fit 1: Fill 2: Cover" tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                [[VePhoneManager sharedInstance] updateVideoRenderMode: [tf.text integerValue]];
            }
        }];
    } else if (btn.tag == 130) {
        [self setCustomViewController: @"请输入目标Uid" hintText: nil tappedSureBlock:^(UITextField *tf) {
            if (tf.text.length > 0) {
                [[VePhoneManager sharedInstance] hasControl: tf.text];
            }
        }];
    } else if (btn.tag == 131) {
        [[VePhoneManager sharedInstance] getAllControls];
    } else if (btn.tag == 132) {
        CustomViewController *alert = [CustomViewController alertControllerWithTitle: @"请输入目标Uid&操控权" message: nil preferredStyle: UIAlertControllerStyleAlert];
        alert.rotation = self.rotation;
        __block UITextField *tf1 = [UITextField new];
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            tf1 = textField;
            tf1.placeholder = @"目标用户的Uid";
            tf1.keyboardType = UIKeyboardTypeDefault;
        }];
        __block UITextField *tf2 = [UITextField new];
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            tf2 = textField;
            tf2.placeholder = @"0: 无操控权；1: 有操控权";
            tf2.keyboardType = UIKeyboardTypeDecimalPad;
        }];
        UIAlertAction *action0 = [UIAlertAction actionWithTitle: @"取消" style:UIAlertActionStyleCancel handler: nil];
        [alert addAction: action0];
        UIAlertAction *action1 = [UIAlertAction actionWithTitle: @"确认" style:UIAlertActionStyleDestructive handler:^(UIAlertAction * _Nonnull action) {
            if (tf1.text.length > 0 && [tf2.text integerValue] != NSNotFound) {
                VePhoneControlState *state = [VePhoneControlState new];
                state.userId = tf1.text;
                state.enable = [tf2.text integerValue];
                [[VePhoneManager sharedInstance] enableControl: state];
            }
        }];
        [alert addAction: action1];
        [self presentViewController: alert animated: NO completion: nil];
    } else if (btn.tag == 133) { // 拦截触控事件
        btn.selected = !btn.selected;
        [[VePhoneManager sharedInstance] setInterceptSendTouchEvent: btn.selected];
        [btn setTitle: btn.selected ? @"禁止触控事件" : @"开启触控事件" forState: UIControlStateNormal];
    }
}

- (void)setupAudioSession
{
    // 1、获取音频会话实例
    AVAudioSession *session = [AVAudioSession sharedInstance];
    NSError *error = nil;
    // 2、设置分类和选项
    [session setCategory:AVAudioSessionCategoryPlayAndRecord withOptions:AVAudioSessionCategoryOptionMixWithOthers | AVAudioSessionCategoryOptionDefaultToSpeaker error:&error];
    if (error) {
        NSLog(@"AVAudioSession setCategory error.");
        error = nil;
        return;
    }
    // 3、设置模式
    [session setMode:AVAudioSessionModeVideoRecording error:&error];
    if (error) {
        NSLog(@"AVAudioSession setMode error.");
        error = nil;
        return;
    }
    // 4、激活会话
    [session setActive:YES error:&error];
    if (error) {
        NSLog(@"AVAudioSession setActive error.");
        error = nil;
        return;
    }
}

- (void)setCustomViewController:(NSString *)title hintText:(NSString *)hint tappedSureBlock:(void(^)(UITextField *tf))block
{
    __block UITextField *tf = [UITextField new];
    CustomViewController *alert = [CustomViewController alertControllerWithTitle: title message: nil preferredStyle: UIAlertControllerStyleAlert];
    alert.rotation = self.rotation;
    [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
        textField.placeholder = hint;
        textField.keyboardType = UIKeyboardTypeDefault;
        tf = textField;
    }];
    UIAlertAction *action0 = [UIAlertAction actionWithTitle: @"取消" style:UIAlertActionStyleCancel handler: nil];
    [alert addAction: action0];
    UIAlertAction *action1 = [UIAlertAction actionWithTitle: @"确认" style:UIAlertActionStyleDestructive handler:^(UIAlertAction * _Nonnull action) {
        !block ?: block(tf);
    }];
    [alert addAction: action1];
    [self presentViewController: alert animated: NO completion: nil];
}

#pragma mark - UIImagePickerControllerDelegate

- (void)imagePickerController:(UIImagePickerController *)picker didFinishPickingMediaWithInfo:(NSDictionary<UIImagePickerControllerInfoKey, id> *)info
{
    [picker dismissViewControllerAnimated:YES completion:nil];
    UIImage *image = [info objectForKey:UIImagePickerControllerOriginalImage];
    NSURL *imageurl = [info objectForKey:UIImagePickerControllerMediaURL];
    NSLog(@"%@", imageurl);
    NSData *imageData;
    if (UIImagePNGRepresentation(image)) {
        imageData = UIImagePNGRepresentation(image);
    } else {
        imageData = UIImageJPEGRepresentation(image, 1.0);
    }
    CustomViewController *alert = [CustomViewController alertControllerWithTitle:nil message:@"输入拉取路径" preferredStyle:UIAlertControllerStyleAlert];
    alert.rotation = self.rotation;
    __block NSString *target;
    __block UITextField *tf1;
    __block UITextField *tf2;
    [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
        textField.placeholder = @"请输入推送的文件名";
        textField.text = @"test.png";
        tf1 = textField;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
        textField.placeholder = @"请输入推送路径";
        textField.text = @"/sdcard/Download";
        tf2 = textField;
    }];
    VeFile *file = [VeFile new];
    file.fileData = imageData;
    file.name = tf1.text;
    file.md5 = [self md5String:imageData];
    target = tf2.text;
    UIAlertAction *leftAction = [UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
        [[VePhoneManager sharedInstance] startPushFile:file target:target onStart:^(VeFile *file) {
            NSLog(@"推送文件开始-------%@\n", file);
        } onProgress:^(VeFile *file, NSInteger progress) {
            [SVProgressHUD showProgress:progress / 100.0 status:[NSString stringWithFormat:@"文件拉取中(%ld)%%", progress]];
            NSLog(@"推送文件进度-------%ld\n", progress);
        } onComplete:^(VeFile *file) {
            [SVProgressHUD dismiss];
            NSLog(@"推送文件完成-------%@\n", file);
        } onCancel:^(VeFile *file) {
            NSLog(@"推送文件取消-------%@\n", file);
        } onError:^(VeFile *file, VePhoneErrorCode err) {
            NSLog(@"推送文件出错-------%@\n", file);
        }];
    }];
    [alert addAction:leftAction];
    dispatch_async(dispatch_get_main_queue(), ^{
        [self presentViewController:alert animated:NO completion:nil];
    });
}

- (NSString *)md5String:(NSData *)data
{
    unsigned char result[CC_MD5_DIGEST_LENGTH];
    CC_MD5(data.bytes, (CC_LONG)data.length, result);
    return [NSString stringWithFormat:
            @"%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x",
            result[0], result[1], result[2], result[3],
            result[4], result[5], result[6], result[7],
            result[8], result[9], result[10], result[11],
            result[12], result[13], result[14], result[15]
            ];
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
        if (rotation == 0) {
            [self.scrollView mas_updateConstraints:^(MASConstraintMaker *make) {
                make.left.mas_equalTo(self.view).offset(20.0f);
                make.top.mas_equalTo(self.view).offset(44);
            }];
        } else {
            [self.scrollView mas_updateConstraints:^(MASConstraintMaker *make) {
                make.top.mas_equalTo(self.view).offset(20.0f);
                make.left.mas_equalTo(self.view).offset(44);
            }];
        }
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.5f * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            UIButton *menuBtn = [self.view viewWithTag: 999];
            menuBtn.center = CGPointMake(self.view.bounds.size.width - menuBtn.bounds.size.width / 2, self.view.bounds.size.height / 2 + menuBtn.bounds.size.height);
            [self.scrollView setContentOffset: CGPointMake(0, 0) animated: NO];
        });
    }
}

#pragma mark - getter

- (AudioCaptureConfig *)audioCaptureConfig
{
    if (_audioCaptureConfig == nil) {
        _audioCaptureConfig = [AudioCaptureConfig defaultConfig];
    }
    
    return _audioCaptureConfig;
}

- (AudioCaptureTool *)audioCapture
{
    if (_audioCapture == nil) {
        __weak typeof(self) weakSelf = self;
        _audioCapture = [[AudioCaptureTool alloc] initWithConfig: self.audioCaptureConfig];
        // 音频采集错误回调
        _audioCapture.errorCallBack = ^(NSError* error) {
            NSLog(@"音频采集出错，Error: %zi %@", error.code, error.localizedDescription);
        };
        // 音频采集数据回调
        _audioCapture.sampleBufferOutputCallBack = ^(CMSampleBufferRef sampleBuffer, UInt32 inNumberFrames) {
            if (sampleBuffer) {
                // 1、获取 CMBlockBuffer，这里面封装着 PCM 数据
                CMBlockBufferRef blockBuffer = CMSampleBufferGetDataBuffer(sampleBuffer);
                size_t lengthAtOffsetOutput, totalLengthOutput;
                char *dataPointer;
                // 2、从 CMBlockBuffer 中获取 PCM 数据
                CMBlockBufferGetDataPointer(blockBuffer, 0, &lengthAtOffsetOutput, &totalLengthOutput, &dataPointer);
                NSData *data = [NSData dataWithBytes: dataPointer length: totalLengthOutput];
                // 3、推送到 VePhoneManagerSDK
                VeBaseAudioFrame *audioFrame = [VeBaseAudioFrame new];
                audioFrame.buffer = data;
                audioFrame.samples = inNumberFrames;
                audioFrame.channel = (VeBaseAudioChannel)weakSelf.audioCaptureConfig.channels;
                audioFrame.sampleRate = (VeBaseAudioSampleRate)weakSelf.audioCaptureConfig.sampleRate;
                [[VePhoneManager sharedInstance] pushExternalAudioFrame: audioFrame];
            }
        };
    }
    return _audioCapture;
}

- (VideoCaptureConfig *)videoCaptureConfig
{
    if (!_videoCaptureConfig) {
        _videoCaptureConfig = [[VideoCaptureConfig alloc] init];
        // 由于我们的想要从采集的图像数据里直接转换并存储图片，所以我们这里设置采集处理的颜色空间格式为 32bit BGRA，这样方便将 CMSampleBuffer 转换为 UIImage。
        // _videoCaptureConfig.pixelFormatType = kCVPixelFormatType_32BGRA;
    }
    
    return _videoCaptureConfig;
}

- (VideoCaptureTool *)videoCapture
{
    if (!_videoCapture) {
        _videoCapture = [[VideoCaptureTool alloc] initWithConfig:self.videoCaptureConfig];
        __weak typeof(self) weakSelf = self;
        _videoCapture.sessionInitSuccessCallBack = ^() {
            dispatch_async(dispatch_get_main_queue(), ^{
                [weakSelf.view.layer addSublayer: weakSelf.videoCapture.previewLayer];
                weakSelf.videoCapture.previewLayer.frame = weakSelf.localVideoView.frame;
            });
        };
        _videoCapture.sampleBufferOutputCallBack = ^(CMSampleBufferRef sample) {
            CVPixelBufferRef pixelBuffer = CMSampleBufferGetImageBuffer(sample);
            CMTime timeStamp = CMSampleBufferGetPresentationTimeStamp(sample);
            // 推送到 VePhoneManagerSDK
            [[VePhoneManager sharedInstance] pushExternalVideoFrame: pixelBuffer
                                                               time: timeStamp
                                                           rotation: VeBaseVideoRotation0];
        };
        _videoCapture.sessionErrorCallBack = ^(NSError* error) {
            NSLog(@"KFVideoCapture Error:%zi %@", error.code, error.localizedDescription);
        };
        VeBaseVideoSolution *solution = [VeBaseVideoSolution new];
        solution.width = 1080;
        solution.height = 1920;
        solution.frameRate = 30;
        solution.minBitrate = 1000;
        solution.maxBitrate = 3000;
        [[VePhoneManager sharedInstance] setVideoEncoderConfig: @[solution]];
    }
    
    return _videoCapture;
}

#pragma mark - receive notification

- (void)receiveAppWillTerminateNotification:(NSNotification *)notification
{
    [[VePhoneManager sharedInstance] stop];
}

- (void)receiveAppDidEnterBackgroundNotification:(NSNotification *)notification
{
    [[VePhoneManager sharedInstance] switchPaused: YES];
}

- (void)receiveAppWillEnterForegroundNotification:(NSNotification *)notification
{
    [[VePhoneManager sharedInstance] switchPaused: NO];
}

- (BOOL)shouldAutorotate
{
    return YES;
}

- (UIInterfaceOrientationMask)supportedInterfaceOrientations
{
    UIInterfaceOrientationMask mask = UIInterfaceOrientationMaskPortrait;
    if (self.rotation == 90 || self.rotation == 270) {
        mask = UIInterfaceOrientationMaskLandscapeRight;
    }
    return mask;
}

- (UIInterfaceOrientation)preferredInterfaceOrientationForPresentation
{
    return UIInterfaceOrientationPortrait;
}

- (void)dealloc
{
    NSLog(@"--- VeCloudPhoneDisplayViewController Dealloc ---");
}

@end

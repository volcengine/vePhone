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

@implementation VeCloudPhoneConfigObject

@end

@interface VePhoneDisplayViewController () <VePhoneManagerDelegate, UIImagePickerControllerDelegate, UINavigationControllerDelegate>

@property (nonatomic, strong) UIView *liveView;
@property (nonatomic, strong) UILabel *logLabel;
@property (nonatomic, assign) NSInteger rotation;
@property (nonatomic, strong) UIView *containerView;
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

{
    BOOL _isNavShow;
}

- (void)viewDidLoad
{
    [super viewDidLoad];
    
    [self configSubView];
    [self setupAudioSession];
    
    self.rotation = 0;
    [SVProgressHUD showWithStatus: @"正在启动..."];
    // 初始化云手机实例
    [VePhoneManager sharedInstance].containerView = self.containerView;
    [VePhoneManager sharedInstance].delegate = self;
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
    configObj.autoRecycleTime = self.configObj.autoRecycleTime;
    // configObj.remoteWindowSize = CGSizeMake(0, 0);
    // configObj.videoRenderMode = VeBaseVideoRenderModeFit;
    // 虚拟定位
    VeBaseLocationInfo *location = [VeBaseLocationInfo new];
    location.latitude = [UserInfoManager sharedInstance].latitude;
    location.longitude = [UserInfoManager sharedInstance].longitude;
//    configObj.remoteLocationMock = location;
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
    
    // 退出按钮
    UIButton *exitButton = [UIButton buttonWithType: UIButtonTypeCustom];
    exitButton.tag = 100;
    [exitButton setBackgroundImage: [UIImage imageNamed: @"close"] forState: UIControlStateNormal];
    [exitButton addTarget: self action: @selector(tappedTestButton:) forControlEvents: UIControlEventTouchUpInside];
    [self.view addSubview: exitButton];
    [exitButton mas_makeConstraints:^(MASConstraintMaker *make) {
        make.left.mas_equalTo(self.view).offset(35.0f);
        make.size.mas_equalTo(CGSizeMake(30.0f, 30.0f));
        make.top.mas_equalTo(self.view.mas_top).offset(44 + 5.0f);
    }];
    
    // 本地视频采集视图
    self.liveView = ({
        UIView *liveView = [[UIView alloc] init];
        liveView.hidden = YES;
        liveView.backgroundColor = [UIColor blackColor];
        [self.view addSubview: liveView];
        [liveView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.top.mas_equalTo(exitButton);
            make.right.mas_equalTo(self.view).offset(-10.0f);
            make.size.mas_equalTo(CGSizeMake(150.0f, 200.0f));
        }];
        liveView;
    });
    
    // 日志输出
    self.logLabel = ({
        UILabel *logLabel = [[UILabel alloc] init];
        logLabel.numberOfLines = 0;
        logLabel.textColor = [UIColor yellowColor];
        logLabel.textAlignment = NSTextAlignmentLeft;
        logLabel.font = [UIFont systemFontOfSize: 13];
        [self.view addSubview: logLabel];
        [logLabel mas_makeConstraints:^(MASConstraintMaker *make) {
            make.left.mas_equalTo(self.view).offset(35.0f);
            make.right.mas_equalTo(self.view).offset(-35.0f);
            make.bottom.mas_equalTo(self.view).offset(-(34 + 5.0f));
        }];
        logLabel;
    });
    
    // 菜单
    UIButton *menuBtn = [UIButton buttonWithType: UIButtonTypeCustom];
    menuBtn.layer.cornerRadius = 20.0f;
    menuBtn.layer.masksToBounds = YES;
    menuBtn.backgroundColor = [UIColor systemBlueColor];
    menuBtn.titleLabel.font = [UIFont systemFontOfSize: 13.0f];
    [menuBtn setTitle: @"Menu" forState: UIControlStateNormal];
    [menuBtn setTitleColor: [UIColor whiteColor] forState: UIControlStateNormal];
    [menuBtn addTarget: self action: @selector(tappedMenuButton:) forControlEvents: UIControlEventTouchUpInside];
    [self.view addSubview: menuBtn];
    [menuBtn mas_makeConstraints:^(MASConstraintMaker *make) {
        make.right.mas_equalTo(self.view);
        make.size.mas_equalTo(CGSizeMake(40, 40));
        make.bottom.mas_equalTo(self.view).offset(-100);
    }];
    
    self.scrollView = ({
        UIScrollView *scrollView = [[UIScrollView alloc] init];
        scrollView.hidden = YES;
        [self.view addSubview: scrollView];
        [scrollView mas_makeConstraints:^(MASConstraintMaker *make) {
            make.width.mas_equalTo(170);
            make.left.mas_equalTo(exitButton);
            make.top.mas_equalTo(exitButton.mas_bottom).offset(5.0f);
            make.bottom.mas_equalTo(self.logLabel.mas_top).offset(-5.0f);
        }];
        scrollView;
    });
    
    UIView *btnView = [[UIView alloc] init];
    [self.scrollView addSubview: btnView];
    [btnView mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.left.right.bottom.mas_equalTo(self.scrollView);
        make.width.mas_equalTo(self.scrollView);
    }];
    
    UIButton *button1 = [self createButton: @"摄像头类型"];
    button1.tag = 101;
    [btnView addSubview: button1];
    [button1 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(btnView);
        make.left.mas_equalTo(btnView);
        make.size.mas_equalTo(CGSizeMake(80, 40));
    }];
    
    UIButton *button2 = [self createButton: @"镜像开关"];
    button2.tag = 102;
    [btnView addSubview: button2];
    [button2 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button1);
        make.top.mas_equalTo(button1);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button3 = [self createButton: @"发送消息(无回执)"];
    button3.tag = 103;
    [btnView addSubview: button3];
    [button3 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button1);
        make.left.mas_equalTo(button1);
        make.top.mas_equalTo(button1.mas_bottom).offset(10);
    }];
    
    UIButton *button4 = [self createButton: @"发送消息(超时3秒)"];
    button4.tag = 104;
    [btnView addSubview: button4];
    [button4 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button3);
        make.top.mas_equalTo(button3);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button5 = [self createButton: @"发送消息(uid，无回执)"];
    button5.tag = 105;
    [btnView addSubview: button5];
    [button5 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button3);
        make.left.mas_equalTo(button3);
        make.top.mas_equalTo(button3.mas_bottom).offset(10);
    }];
    
    UIButton *button6 = [self createButton: @"发送消息(uid，超时3秒)"];
    button6.tag = 106;
    [btnView addSubview: button6];
    [button6 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button5);
        make.size.mas_equalTo(button5);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button7 = [self createButton: @"截图"];
    button7.tag = 107;
    [btnView addSubview: button7];
    [button7 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button5);
        make.left.mas_equalTo(button5);
        make.top.mas_equalTo(button5.mas_bottom).offset(10);
    }];
    
    UIButton *button8 = [self createButton: @"键盘事件"];
    button8.tag = 108;
    [btnView addSubview: button8];
    [button8 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button7);
        make.size.mas_equalTo(button7);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button9 = [self createButton: @"焦点应用包名"];
    button9.tag = 109;
    [btnView addSubview: button9];
    [button9 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button7);
        make.left.mas_equalTo(button7);
        make.top.mas_equalTo(button7.mas_bottom).offset(10);
    }];
    
    UIButton *button10 = [self createButton: @"清晰度切换"];
    button10.tag = 110;
    [btnView addSubview: button10];
    [button10 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button9);
        make.size.mas_equalTo(button9);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button11 = [self createButton: @"设置无操作回收时长"];
    button11.tag = 111;
    [btnView addSubview: button11];
    [button11 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button9);
        make.left.mas_equalTo(button9);
        make.top.mas_equalTo(button9.mas_bottom).offset(10);
    }];
    
    UIButton *button12 = [self createButton: @"获取无操作回收时长"];
    button12.tag = 112;
    [btnView addSubview: button12];
    [button12 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button11);
        make.size.mas_equalTo(button11);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button13 = [self createButton: @"设置后台保活时长"];
    button13.tag = 113;
    [btnView addSubview: button13];
    [button13 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button11);
        make.left.mas_equalTo(button11);
        make.top.mas_equalTo(button11.mas_bottom).offset(10);
    }];
    
    UIButton *button14 = [self createButton: @"切换前后台"];
    button14.tag = 114;
    [btnView addSubview: button14];
    [button14 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button13);
        make.size.mas_equalTo(button13);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button15 = [self createButton: self.configObj.streamType == VeBaseStreamTypeVideo ? @"静音打开" : @"静音关闭"];
    button15.tag = 115;
    [btnView addSubview: button15];
    button15.selected = self.configObj.streamType == VeBaseStreamTypeVideo;
    [button15 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button13);
        make.left.mas_equalTo(button13);
        make.top.mas_equalTo(button13.mas_bottom).offset(10);
    }];
    
    UIButton *button16 = [self createButton: self.configObj.streamType == VeBaseStreamTypeAudio ? @"视频暂停" : @"视频播放"];
    button16.tag = 116;
    [btnView addSubview: button16];
    button16.selected = self.configObj.streamType == VeBaseStreamTypeAudio;
    [button16 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button15);
        make.size.mas_equalTo(button15);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button17 = [self createButton: @"采集视图隐藏"];
    button17.tag = 117;
    [btnView addSubview: button17];
    [button17 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button15);
        make.left.mas_equalTo(button15);
        make.top.mas_equalTo(button15.mas_bottom).offset(10);
    }];
    
    UIButton *button18 = [self createButton: @"音频播放设备"];
    button18.tag = 118;
    [btnView addSubview: button18];
    [button18 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button17);
        make.size.mas_equalTo(button17);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button19 = [self createButton: @"剪切板"];
    button19.tag = 119;
    [btnView addSubview: button19];
    [button19 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button17);
        make.left.mas_equalTo(button17);
        make.top.mas_equalTo(button17.mas_bottom).offset(10);
    }];
    
    UIButton *button20 = [self createButton: @"开始录屏"];
    button20.tag = 120;
    [btnView addSubview: button20];
    [button20 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button19);
        make.size.mas_equalTo(button19);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button21 = [self createButton: @"推送文件"];
    button21.tag = 121;
    [btnView addSubview: button21];
    [button21 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button19);
        make.left.mas_equalTo(button19);
        make.top.mas_equalTo(button19.mas_bottom).offset(10);
    }];
    
    UIButton *button22 = [self createButton: @"拉取文件"];
    button22.tag = 122;
    [btnView addSubview: button22];
    [button22 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button21);
        make.size.mas_equalTo(button21);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button23 = [self createButton: @"切换远端应用到前台"];
    button23.tag = 123;
    [btnView addSubview: button23];
    [button23 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button21);
        make.left.mas_equalTo(button21);
        make.top.mas_equalTo(button21.mas_bottom).offset(10);
    }];
    
    UIButton *button24 = [self createButton: @"获取后台APP列表"];
    button24.tag = 124;
    [btnView addSubview: button24];
    [button24 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button23);
        make.size.mas_equalTo(button23);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button25 = [self createButton: @"设置导航条"];
    button25.tag = 125;
    [btnView addSubview: button25];
    [button25 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button23);
        make.left.mas_equalTo(button23);
        make.top.mas_equalTo(button23.mas_bottom).offset(10);
    }];
    
    UIButton *button26 = [self createButton: @"获取导航条状态"];
    button26.tag = 126;
    [btnView addSubview: button26];
    [button26 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.top.mas_equalTo(button25);
        make.size.mas_equalTo(button25);
        make.right.mas_equalTo(btnView);
    }];
    
    UIButton *button27 = [self createButton: @"渲染模式"];
    button27.tag = 127;
    [btnView addSubview: button27];
    [button27 mas_makeConstraints:^(MASConstraintMaker *make) {
        make.size.mas_equalTo(button25);
        make.left.mas_equalTo(button25);
        make.top.mas_equalTo(button25.mas_bottom).offset(10);
        make.bottom.mas_equalTo(btnView);
    }];
}

#pragma mark - VePhoneManagerDelegate

- (void)firstRemoteAudioFrameArrivedFromEngineManager:(VePhoneManager *)manager
{
    if (manager.streamType == VeBaseStreamTypeAudio) {
        [SVProgressHUD dismiss];
    }
}

- (void)phoneManager:(VePhoneManager *)manager startSucceedResult:(NSInteger)streamProfileId reservedId:(NSString *)reservedId extra:(NSDictionary *)extra
{
    [SVProgressHUD dismiss];
    [manager setLocalVideoCanvas: self.liveView];
}

- (void)phoneManager:(VePhoneManager *)manager changedDeviceRotation:(NSInteger)rotation
{
    self.rotation = rotation;
}

- (void)phoneManager:(VePhoneManager *)manager operationDelay:(NSInteger)delayTime
{
    self.operationDelayTime = [NSString stringWithFormat: @"操作延迟: %ldms", (long)delayTime];
}

- (void)phoneManager:(VePhoneManager *)manager onLocalStreamStats:(VeBaseLocalStreamStats *)stats
{
    // NSLog(@"local stream stats: %@", [stats description]);
}

- (void)phoneManager:(VePhoneManager *)manager onRemoteStreamStats:(VeBaseRemoteStreamStats *)stats
{
    dispatch_async(dispatch_get_main_queue(), ^{
        self.logLabel.text = [NSString stringWithFormat: @"%@ 音频rtt: %ldms 视频rtt: %ldms 音频码率: %ldkbps 视频码率: %ldkbps", self.operationDelayTime, (long)stats.audioRtt, (long)stats.videoRtt, (long)stats.receivedAudioKBitrate, (long)stats.receivedVideoKBitrate];
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

- (void)phoneManager:(VePhoneManager *)manager onAudioCaptureDeviceStartState:(BOOL)success
{
    [SVProgressHUD dismiss];
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

- (void)phoneManager:(VePhoneManager *)manager switchVideoStreamProfileWithCode:(NSInteger)code fromIndex:(NSInteger)index1 toIndex:(NSInteger)index2
{
    NSString *toast = [NSString stringWithFormat: @"清晰度切换：%@，fromIndex = %@, toIndex = %@", code == 0 ? @"成功" : @"失败", @(index1), @(index2)];
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
    [self.view makeToast: toast
                duration: 2.0f
                position: CSToastPositionCenter];
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

- (void)phoneManager:(VePhoneManager *)manager
              status:(VeBaseRecordingStatus)status
            savePath:(NSString *)savePath
                 msg:(NSString *)msg
         downloadUrl:(NSString *)url
{
    NSLog(@"status: %li  savePath: %@ downloadUrl: %@ msg: %@", status, savePath, url, msg);
}

- (void)phoneManager:(VePhoneManager *)manager onNavBarStatus:(NSInteger)status reason:(NSInteger)reason
{
    _isNavShow = status;
    NSLog(@"导航栏%@", status == 0 ? @"隐藏" : @"显示");
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
    button.titleLabel.adjustsFontSizeToFitWidth = YES;
    button.backgroundColor = [UIColor systemBlueColor];
    button.titleLabel.font = [UIFont systemFontOfSize: 13.0f];
    [button setTitle: title forState: UIControlStateNormal];
    [button setTitleColor: [UIColor whiteColor] forState: UIControlStateNormal];
    [button addTarget: self action: @selector(tappedTestButton:) forControlEvents: UIControlEventTouchUpInside];
    return button;
}

- (void)setStreamStats:(NSString *)stats
{
    self.logLabel.text = [NSString stringWithFormat: @"%@ %@", self.operationDelayTime, stats];
}

#pragma mark - button action

- (void)tappedMenuButton:(UIButton *)button
{
    button.selected = !button.selected;
    self.scrollView.hidden = !button.selected;
}

- (void)tappedTestButton:(UIButton *)btn
{
    if (btn.tag == 100) { // 退出
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
        __weak __typeof(self)weakSelf = self;
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
        __weak __typeof(self)weakSelf = self;
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
        self.liveView.hidden = !btn.selected;
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
        VeFile *file = [VeFile new];
        file.name = @"1.png";
        file.podFilePath = @"/sdcard/Download/";
        [[VePhoneManager sharedInstance] startPullFile:file onStart:^(VeFile *file) {
            NSLog(@"拉取文件开始-------%@\n", file);
        } onProgress:^(VeFile *file, NSInteger progress) {
            [SVProgressHUD showProgress:progress / 100.0 status:[NSString stringWithFormat:@"文件拉取中(%ld)%%", progress]];
            NSLog(@"拉取文件进度-------%ld\n", progress);
        } onComplete:^(VeFile *file, NSString *url) {
            [SVProgressHUD dismiss];
            NSLog(@"拉取文件完成-------%@\n", url);
            CustomViewController *alert = [CustomViewController alertControllerWithTitle:nil message:@"文件拉取完成，是否打开？" preferredStyle:UIAlertControllerStyleAlert];
            alert.rotation = self.rotation;
            UIAlertAction *leftAction = [UIAlertAction actionWithTitle:@"取消" style:UIAlertActionStyleCancel handler:nil];
            UIAlertAction *rightAction = [UIAlertAction actionWithTitle:@"打开" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
                if (url && [[UIApplication sharedApplication] canOpenURL:[NSURL URLWithString:url]]) {
                    [[UIApplication sharedApplication] openURL:[NSURL URLWithString:url]];
                } else {
                    [SVProgressHUD showInfoWithStatus:@"文件打开失败"];
                }
            }];
            [alert addAction:leftAction];
            [alert addAction:rightAction];
            [self presentViewController:alert animated:NO completion:nil];
        } onCancel:^(VeFile *file) {
            NSLog(@"取消拉取文件-------%@\n", file);
        } onError:^(VeFile *file, VePhoneErrorCode err) {
            NSLog(@"拉取文件错误-------%@\n", file);
        }];
    } else if (btn.tag == 123) {
        [self setCustomViewController: @"切换远端App到前台" hintText: @"请输入packageName" tappedSureBlock:^(UITextField *tf) {
            if (tf.text.length != 0) {
                [[VePhoneManager sharedInstance] setRemoteAppForeground: tf.text];
            }
        }];
    } else if (btn.tag == 124) {
        [[VePhoneManager sharedInstance] getRemoteBackgroundAppList];
    } else if (btn.tag == 125) {
        [[VePhoneManager sharedInstance] setNavBarStatus: !_isNavShow];
    } else if (btn.tag == 126) {
        [[VePhoneManager sharedInstance] getNavBarStatus];
    } else if (btn.tag == 127) {
        [self setCustomViewController: @"设置渲染模式" hintText: @"0: Fit 1: Fill 2: Cover" tappedSureBlock:^(UITextField *tf) {
            if ([tf.text integerValue] != NSNotFound) {
                [[VePhoneManager sharedInstance] updateVideoRenderMode: [tf.text integerValue]];
            }
        }];
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
        textField.keyboardType = UIKeyboardTypeDecimalPad;
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
    VeFile *file = [VeFile new];
    file.fileData = imageData;
    file.name = @"1.png";
    file.md5 = [self md5Str:imageData];
    [[VePhoneManager sharedInstance] startPushFile:file target:@"/sdcard/Download" onStart:^(VeFile *file) {
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
}

- (NSString *)md5Str:(NSData *)strData {
    unsigned char result[CC_MD5_DIGEST_LENGTH];
    CC_MD5(strData.bytes, (CC_LONG)strData.length, result);
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
        UIView *exitBtn = [self.view viewWithTag: 100];
        if (rotation == 0) {
            [exitBtn mas_updateConstraints:^(MASConstraintMaker *make) {
                make.left.mas_equalTo(self.view).offset(35.0f);
                make.top.mas_equalTo(self.view.mas_top).offset(44 + 5.0f);
            }];
        } else {
            [exitBtn mas_updateConstraints:^(MASConstraintMaker *make) {
                make.top.mas_equalTo(self.view.mas_top).offset(20.0f);
                make.left.mas_equalTo(self.view).offset(44);
            }];
        }
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
                weakSelf.videoCapture.previewLayer.frame = weakSelf.liveView.frame;
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
        solution.maxBitrate = 2000;
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

- (void)dealloc
{
    NSLog(@"--- VeCloudPhoneDisplayViewController Dealloc ---");
}

@end

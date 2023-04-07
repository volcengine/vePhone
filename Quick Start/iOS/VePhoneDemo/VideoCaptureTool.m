//
//  VideoCaptureTool.m
//  VePlayerDemo
//
//  Created by changwuguo on 2022/12/2.
//  Copyright © 2022 ByteDance Ltd. All rights reserved.
//

#import "VideoCaptureTool.h"
#import <UIKit/UIKit.h>

@implementation VideoCaptureConfig

- (instancetype)init
{
    if (self = [super init]) {
        _preset = AVCaptureSessionPreset1920x1080;
        _position = AVCaptureDevicePositionFront;
        _orientation = AVCaptureVideoOrientationPortrait;
        _fps = 30;
        _mirrorType = VideoCaptureMirrorFront;
        // 设置颜色空间格式，这里要注意了：
        // 1、一般我们采集图像用于后续的编码时，这里设置 kCVPixelFormatType_420YpCbCr8BiPlanarFullRange 即可。
        // 2、如果想支持 HDR 时（iPhone12 及之后设备才支持），这里设置为：kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange。
        _pixelFormatType = kCVPixelFormatType_420YpCbCr8BiPlanarFullRange;
    }
    
    return self;
}

@end

@interface VideoCaptureTool () <AVCaptureVideoDataOutputSampleBufferDelegate>

@property (nonatomic, strong, readwrite) VideoCaptureConfig *config;
// 视频采集设备
@property (nonatomic, strong, readonly) AVCaptureDevice *captureDevice;
// 后置摄像头采集输入
@property (nonatomic, strong) AVCaptureDeviceInput *backDeviceInput;
// 前置摄像头采集输入
@property (nonatomic, strong) AVCaptureDeviceInput *frontDeviceInput;
// 视频采集输出
@property (nonatomic, strong) AVCaptureVideoDataOutput *videoOutput;
// 视频采集会话
@property (nonatomic, strong) AVCaptureSession *captureSession;
// 视频预览渲染 layer
@property (nonatomic, strong, readwrite) AVCaptureVideoPreviewLayer *previewLayer;
// 视频采集分辨率
@property (nonatomic, assign, readonly) CMVideoDimensions sessionPresetSize;

@property (nonatomic, strong) dispatch_queue_t captureQueue;

@end

@implementation VideoCaptureTool

- (AVCaptureDevice *)backCamera
{
    return [self cameraWithPosition:AVCaptureDevicePositionBack];
}

- (AVCaptureDeviceInput *)backDeviceInput
{
    if (!_backDeviceInput) {
        _backDeviceInput = [[AVCaptureDeviceInput alloc] initWithDevice:[self backCamera] error:nil];
    }
    
    return _backDeviceInput;
}

- (AVCaptureDevice *)frontCamera
{
    return [self cameraWithPosition:AVCaptureDevicePositionFront];
}

- (AVCaptureDeviceInput *)frontDeviceInput
{
    if (!_frontDeviceInput) {
        _frontDeviceInput = [[AVCaptureDeviceInput alloc] initWithDevice:[self frontCamera] error:nil];
    }
    
    return _frontDeviceInput;
}

- (AVCaptureVideoDataOutput *)videoOutput
{
    if (!_videoOutput) {
        _videoOutput = [[AVCaptureVideoDataOutput alloc] init];
        // 设置返回采集数据的代理和回调
        [_videoOutput setSampleBufferDelegate:self queue:self.captureQueue];
        _videoOutput.videoSettings = @{(id)kCVPixelBufferPixelFormatTypeKey: @(_config.pixelFormatType)};
        // YES 表示：采集的下一帧到来前，如果有还未处理完的帧，丢掉
        _videoOutput.alwaysDiscardsLateVideoFrames = YES;
    }

    return _videoOutput;
}

- (AVCaptureSession *)captureSession
{
    if (!_captureSession) {
        AVCaptureDeviceInput *deviceInput = self.config.position == AVCaptureDevicePositionBack ? self.backDeviceInput : self.frontDeviceInput;
        if (!deviceInput) {
            return nil;
        }
        // 1、初始化采集会话
        _captureSession = [[AVCaptureSession alloc] init];
        // 2、添加采集输入
        for (AVCaptureSessionPreset selectPreset in [self sessionPresetList]) {
            if ([_captureSession canSetSessionPreset:selectPreset]) {
                [_captureSession setSessionPreset:selectPreset];
                if ([_captureSession canAddInput:deviceInput]) {
                    [_captureSession addInput:deviceInput];
                    break;
                }
            }
        }
        // 3、添加采集输出
        if ([_captureSession canAddOutput:self.videoOutput]) {
            [_captureSession addOutput:self.videoOutput];
        }
        // 4、更新画面方向
        [self _updateOrientation];
        // 5、更新画面镜像
        [self _updateMirror];
        // 6、更新采集实时帧率
        [self.captureDevice lockForConfiguration:nil];
        [self _updateActiveFrameDuration];
        [self.captureDevice unlockForConfiguration];
        // 7、回报成功
        if (self.sessionInitSuccessCallBack) {
            self.sessionInitSuccessCallBack();
        }
    }
    
    return _captureSession;
}

- (AVCaptureVideoPreviewLayer *)previewLayer
{
    if (!_captureSession) {
        return nil;
    }
    if (!_previewLayer) {
        // 初始化预览渲染 layer。这里就直接用系统提供的 API 来渲染。
        _previewLayer = [[AVCaptureVideoPreviewLayer alloc] initWithSession:_captureSession];
        [_previewLayer setVideoGravity:AVLayerVideoGravityResizeAspectFill];
    }
    return _previewLayer;
}

- (AVCaptureDevice *)captureDevice
{
    // 视频采集设备
    return (self.config.position == AVCaptureDevicePositionBack) ? [self backCamera] : [self frontCamera];
}

- (CMVideoDimensions)sessionPresetSize
{
    // 视频采集分辨率
    return CMVideoFormatDescriptionGetDimensions([self captureDevice].activeFormat.formatDescription);
}

- (instancetype)initWithConfig:(VideoCaptureConfig *)config
{
    if (self = [super init]) {
        _config = config;
        _captureQueue = dispatch_queue_create("com.VePlayerDemo.VideoCapture", DISPATCH_QUEUE_SERIAL);
        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(sessionRuntimeError:) name:AVCaptureSessionRuntimeErrorNotification
                                                   object:nil];
    }
    
    return self;
}

- (void)dealloc
{
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)start
{
    typeof(self) __weak weakSelf = self;
    dispatch_async(_captureQueue, ^{
        [weakSelf _start];
    });
}

- (void)stop
{
    typeof(self) __weak weakSelf = self;
    dispatch_async(_captureQueue, ^{
        [weakSelf _stop];
    });
}

- (void)changeDevicePosition:(AVCaptureDevicePosition)position
{
    typeof(self) __weak weakSelf = self;
    dispatch_async(_captureQueue, ^{
        [weakSelf _updateDeveicePosition: position];
    });
}

- (void)_start
{
    AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
    if (status == AVAuthorizationStatusAuthorized) {
        if (!self.captureSession.isRunning) {
            [self.captureSession startRunning];
        }
    } else {
        NSLog(@"没有相机使用权限");
    }
}

- (void)_stop
{
    if (_captureSession && _captureSession.isRunning) {
        [_captureSession stopRunning];
    }
}

- (void)_updateDeveicePosition:(AVCaptureDevicePosition)position
{
    // 切换采集的摄像头
    if (position == self.config.position || !_captureSession.isRunning) {
        return;
    }
    // 1、切换采集输入
    AVCaptureDeviceInput *curInput = self.config.position == AVCaptureDevicePositionBack ? self.backDeviceInput : self.frontDeviceInput;
    AVCaptureDeviceInput *addInput = self.config.position == AVCaptureDevicePositionBack ? self.frontDeviceInput : self.backDeviceInput;
    if (!curInput || !addInput) {
        return;
    }
    [self.captureSession removeInput:curInput];
    for (AVCaptureSessionPreset selectPreset in [self sessionPresetList]) {
        if ([_captureSession canSetSessionPreset:selectPreset]) {
            [_captureSession setSessionPreset:selectPreset];
            if ([_captureSession canAddInput:addInput]) {
                [_captureSession addInput:addInput];
                self.config.position = position;
                break;
            }
        }
    }
    // 2、更新画面方向
    [self _updateOrientation];
    // 3、更新画面镜像
    [self _updateMirror];
    // 4、更新采集实时帧率
    [self.captureDevice lockForConfiguration:nil];
    [self _updateActiveFrameDuration];
    [self.captureDevice unlockForConfiguration];
}

- (void)_updateOrientation
{
    // 更新画面方向。
    AVCaptureConnection *connection = [self.videoOutput connectionWithMediaType:AVMediaTypeVideo]; // AVCaptureConnection 用于把输入和输出连接起来。
    if ([connection isVideoOrientationSupported] && connection.videoOrientation != self.config.orientation) {
        connection.videoOrientation = self.config.orientation;
    }
}

- (void)_updateMirror
{
    // 更新画面镜像。
    AVCaptureConnection *connection = [self.videoOutput connectionWithMediaType:AVMediaTypeVideo];
    if ([connection isVideoMirroringSupported]) {
        if ((self.config.mirrorType & VideoCaptureMirrorFront) && self.config.position == AVCaptureDevicePositionFront) {
            connection.videoMirrored = YES;
        } else if ((self.config.mirrorType & VideoCaptureMirrorBack) && self.config.position == AVCaptureDevicePositionBack) {
            connection.videoMirrored = YES;
        } else {
            connection.videoMirrored = NO;
        }
    }
}

- (BOOL)_updateActiveFrameDuration
{
    // 更新采集实时帧率。
    // 1、帧率换算成帧间隔时长
    CMTime frameDuration = CMTimeMake(1, (int32_t) self.config.fps);
    // 2、设置帧率大于 30 时，找到满足该帧率及其他参数，并且当前设备支持的 AVCaptureDeviceFormat
    if (self.config.fps > 30) {
        for (AVCaptureDeviceFormat *vFormat in [self.captureDevice formats]) {
            CMFormatDescriptionRef description = vFormat.formatDescription;
            CMVideoDimensions dims = CMVideoFormatDescriptionGetDimensions(description);
            float maxRate = ((AVFrameRateRange *) [vFormat.videoSupportedFrameRateRanges objectAtIndex:0]).maxFrameRate;
            if (maxRate >= self.config.fps && CMFormatDescriptionGetMediaSubType(description) == self.config.pixelFormatType && self.sessionPresetSize.width * self.sessionPresetSize.height == dims.width * dims.height) {
                self.captureDevice.activeFormat = vFormat;
                break;
            }
        }
    }
    // 3、检查设置的帧率是否在当前设备的 activeFormat 支持的最低和最高帧率之间。如果是，就设置帧率
    __block BOOL support = NO;
    [self.captureDevice.activeFormat.videoSupportedFrameRateRanges enumerateObjectsUsingBlock:^(AVFrameRateRange * _Nonnull obj, NSUInteger idx, BOOL * _Nonnull stop) {
        if (CMTimeCompare(frameDuration, obj.minFrameDuration) >= 0 &&
            CMTimeCompare(frameDuration, obj.maxFrameDuration) <= 0) {
            support = YES;
            *stop = YES;
        }
    }];
    if (support) {
        [self.captureDevice setActiveVideoMinFrameDuration:frameDuration];
        [self.captureDevice setActiveVideoMaxFrameDuration:frameDuration];
        return YES;
    }
    
    return NO;
}

#pragma mark - NSNotification

- (void)sessionRuntimeError:(NSNotification *)notification
{
    if (self.sessionErrorCallBack) {
        self.sessionErrorCallBack(notification.userInfo[AVCaptureSessionErrorKey]);
    }
}

#pragma mark - Utility

- (AVCaptureDevice *)cameraWithPosition:(AVCaptureDevicePosition)position
{
    // 从当前手机寻找符合需要的采集设备。
    NSArray *devices = nil;
    NSString *version = [UIDevice currentDevice].systemVersion;
    if (version.doubleValue >= 10.0) {
        AVCaptureDeviceDiscoverySession *deviceDiscoverySession = [AVCaptureDeviceDiscoverySession  discoverySessionWithDeviceTypes:@[AVCaptureDeviceTypeBuiltInWideAngleCamera] mediaType:AVMediaTypeVideo position:position];
        devices = deviceDiscoverySession.devices;
    } else {
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
        devices = [AVCaptureDevice devicesWithMediaType:AVMediaTypeVideo];
#pragma GCC diagnostic pop
    }
    
    for (AVCaptureDevice *device in devices) {
        if ([device position] == position) {
            return device;
        }
    }
    
    return nil;
}

- (NSArray *)sessionPresetList
{
    return @[self.config.preset, AVCaptureSessionPreset3840x2160, AVCaptureSessionPreset1920x1080, AVCaptureSessionPreset1280x720, AVCaptureSessionPresetLow];
}

#pragma mark - AVCaptureVideoDataOutputSampleBufferDelegate

- (void)captureOutput:(AVCaptureOutput *)output didOutputSampleBuffer:(CMSampleBufferRef)sampleBuffer fromConnection:(AVCaptureConnection *)connection
{
    // 向外回调数据
    if (output == self.videoOutput) {
        if (self.sampleBufferOutputCallBack) {
            self.sampleBufferOutputCallBack(sampleBuffer);
        }
    }
}


@end

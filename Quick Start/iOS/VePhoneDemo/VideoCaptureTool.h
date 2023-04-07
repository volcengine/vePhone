//
//  VideoCaptureTool.h
//  VePlayerDemo
//
//  Created by changwuguo on 2022/12/2.
//  Copyright © 2022 ByteDance Ltd. All rights reserved.
//

#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>

typedef NS_ENUM(NSInteger, VideoCaptureMirrorType) {
    VideoCaptureMirrorNone = 0,
    VideoCaptureMirrorFront = 1 << 0,
    VideoCaptureMirrorBack = 1 << 1,
    VideoCaptureMirrorAll = (VideoCaptureMirrorFront | VideoCaptureMirrorBack),
};

@interface VideoCaptureConfig : NSObject

// 视频采集参数，比如分辨率等，与画质相关
@property (nonatomic, copy) AVCaptureSessionPreset preset;
// 摄像头位置，前置/后置摄像头
@property (nonatomic, assign) AVCaptureDevicePosition position;
// 视频画面方向
@property (nonatomic, assign) AVCaptureVideoOrientation orientation;
// 视频帧率
@property (nonatomic, assign) NSInteger fps;
// 颜色空间格式
@property (nonatomic, assign) OSType pixelFormatType;
// 镜像类型
@property (nonatomic, assign) VideoCaptureMirrorType mirrorType;

@end

@interface VideoCaptureTool : NSObject

@property (nonatomic, strong, readonly) VideoCaptureConfig *config;
// 视频预览渲染 layer
@property (nonatomic, strong, readonly) AVCaptureVideoPreviewLayer *previewLayer;
// 视频采集数据回调
@property (nonatomic, copy) void (^sampleBufferOutputCallBack)(CMSampleBufferRef sample);
// 视频采集会话错误回调
@property (nonatomic, copy) void (^sessionErrorCallBack)(NSError *error);
// 视频采集会话初始化成功回调
@property (nonatomic, copy) void (^sessionInitSuccessCallBack)(void);

+ (instancetype)new NS_UNAVAILABLE;
- (instancetype)init NS_UNAVAILABLE;
- (instancetype)initWithConfig:(VideoCaptureConfig *)config;

- (void)start;
- (void)stop;
// 切换摄像头
- (void)changeDevicePosition:(AVCaptureDevicePosition)position;

@end

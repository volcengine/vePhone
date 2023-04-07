//
//  AudioCaptureTool.h
//  VePlayerDemo
//
//  Created by changwuguo on 2022/12/1.
//  Copyright © 2022 ByteDance Ltd. All rights reserved.
//

#import <Foundation/Foundation.h>
#import <CoreMedia/CoreMedia.h>

@interface AudioCaptureConfig : NSObject
// 声道数，default: 2
@property (nonatomic, assign) NSUInteger channels;
// 采样率，default: 44100
@property (nonatomic, assign) NSUInteger sampleRate;
// 量化位深，default: 16
@property (nonatomic, assign) NSUInteger bitDepth;

+ (instancetype)defaultConfig;

@end

@interface AudioCaptureTool : NSObject

@property (nonatomic, strong, readonly) AudioCaptureConfig *config;
// 音频采集数据回调
@property (nonatomic, copy) void(^sampleBufferOutputCallBack)(CMSampleBufferRef sample, UInt32 inNumberFrames);
// 音频采集错误回调
@property (nonatomic, copy) void(^errorCallBack)(NSError *error);

+ (instancetype)new NS_UNAVAILABLE;
- (instancetype)init NS_UNAVAILABLE;
- (instancetype)initWithConfig:(AudioCaptureConfig*)config;
// 开始
- (void)start;
// 停止
- (void)stop;

@end

//
//  UserInfoManager.h
//  VePlayerDemo
//
//  Created by Jihua Huang on 2020/8/25.
//  Copyright © 2020 ByteDance Ltd. All rights reserved.
//

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface UserInfoManager : NSObject

+ (instancetype)sharedInstance;
/** 纬度 */
@property (nonatomic, assign) double latitude;
/** 经度 */
@property (nonatomic, assign) double longitude;

@end

NS_ASSUME_NONNULL_END

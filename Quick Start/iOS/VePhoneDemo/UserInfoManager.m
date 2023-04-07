//
//  UserInfoManager.m
//  VePlayerDemo
//
//  Created by Jihua Huang on 2020/8/25.
//  Copyright © 2020 ByteDance Ltd. All rights reserved.
//

#import "Define.h"
#import "UserInfoManager.h"
#import <CoreLocation/CoreLocation.h>

@interface UserInfoManager() <CLLocationManagerDelegate>

@property (nonatomic, strong) CLLocationManager *locationManager;

@end

@implementation UserInfoManager

+ (instancetype)sharedInstance
{
    static dispatch_once_t predicate;
    static UserInfoManager *instance;
    dispatch_once(&predicate, ^{
        instance = [UserInfoManager new];
    });
    return instance;
}

- (instancetype)init
{
    if (self = [super init]) {
        _latitude = 39.9f;
        _longitude = 116.4f;
        [self setupLocationManager];
        [[NSNotificationCenter defaultCenter] addObserver: self.locationManager selector: @selector(startUpdatingLocation) name: UIApplicationWillEnterForegroundNotification object: nil];
    }
    return self;
}

- (void)setupLocationManager
{
    self.locationManager = ({
        CLLocationManager *locationManager = [CLLocationManager new];
        locationManager.delegate = self;
        locationManager.desiredAccuracy = kCLLocationAccuracyThreeKilometers;
        [locationManager requestWhenInUseAuthorization];
        [locationManager startUpdatingLocation];
        locationManager;
    });
}

#pragma mark - CLLocationManagerDelegate

- (void)locationManager:(CLLocationManager *)manager didUpdateLocations:(NSArray<CLLocation *> *)locations
{
    CLLocationCoordinate2D coordinate = locations.firstObject.coordinate;
    [UserInfoManager sharedInstance].longitude = coordinate.longitude;
    [UserInfoManager sharedInstance].latitude = coordinate.latitude;
    [manager stopUpdatingLocation];
}

@end

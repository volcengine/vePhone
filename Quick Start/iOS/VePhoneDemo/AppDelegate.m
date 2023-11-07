//
//  AppDelegate.m
//  DemoTest
//
//  Created by changwuguo on 2021/09/06.
//  Copyright © 2021 ByteDance Ltd. All rights reserved.
//

#import "AppDelegate.h"
#import "VePhoneViewController.h"
#import "VeNavigationController.h"
#import "VePhone/VePhoneManager.h"
#import <SVProgressHUD/SVProgressHUD.h>

@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions
{
    self.window = [[UIWindow alloc] initWithFrame: [UIScreen mainScreen].bounds];
    VePhoneViewController *phoneVc = VIEW_CONTROLLER_FROM_XIB(VePhoneViewController);
    VeNavigationController *nav = [[VeNavigationController alloc] initWithRootViewController: phoneVc];;
    self.window.rootViewController = nav;
    [self.window makeKeyAndVisible];

    [self configNavigationController];
    
    [self configProgressHud];
    
    [self configVePhone];

    return YES;
}

- (void)configNavigationController
{
    if (@available(iOS 15.0, *)) {
        UINavigationBarAppearance *appearance = [[UINavigationBarAppearance alloc] init];
        [appearance configureWithOpaqueBackground];
        appearance.backgroundColor = UIColor.clearColor;
        [appearance setTitleTextAttributes: @{NSForegroundColorAttributeName: [UIColor blackColor], NSFontAttributeName: [UIFont boldSystemFontOfSize: 18.0f]}];
        [[UINavigationBar appearance] setScrollEdgeAppearance: appearance];
        [[UINavigationBar appearance] setStandardAppearance: appearance];
    } else {
        [[UINavigationBar appearance] setBarStyle: UIBarStyleDefault];
        [[UINavigationBar appearance] setShadowImage: [UIImage new]];
        [[UINavigationBar appearance] setBarTintColor: [UIColor whiteColor]];
        [[UINavigationBar appearance] setBackgroundImage: [Utils imageFromColor: [UIColor whiteColor]] forBarMetrics: UIBarMetricsDefault];
        [[UINavigationBar appearance] setTitleTextAttributes: @{NSForegroundColorAttributeName: [UIColor blackColor], NSFontAttributeName: [UIFont boldSystemFontOfSize: 18.0f]}];
    }
}

- (void)configProgressHud
{
    [SVProgressHUD setDefaultStyle: SVProgressHUDStyleDark];
    [SVProgressHUD setDefaultAnimationType: SVProgressHUDAnimationTypeNative];
    [SVProgressHUD setDefaultMaskType: SVProgressHUDMaskTypeBlack];
}

- (void)configVePhone
{
    [[VePhoneManager sharedInstance] initWithAccountId:@"------AccountID------"];
}

- (void)applicationWillResignActive:(UIApplication *)application
{
    // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
    // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
}

- (void)applicationDidEnterBackground:(UIApplication *)application
{
    // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
    // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
}

- (void)applicationWillEnterForeground:(UIApplication *)application
{
    // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
}

- (void)applicationDidBecomeActive:(UIApplication *)application
{
    // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
}

- (void)applicationWillTerminate:(UIApplication *)application
{
    // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
}


@end

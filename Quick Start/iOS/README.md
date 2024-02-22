# vePhone SDK Demo

## 说明

本项目是火山引擎云手机 iOS 客户端 SDK 的快速演示 Demo。获取项目以后，开发者可以快速构建应用，体验云手机服务的主要功能；也能参考其中的代码，在实际的客户端应用中实现相似的功能。

## 环境要求
1. iOS 11.0 及以上系统版本的设备
2. 使用 Objective-C 开发语言
3. VePhone.framework 为 Dynamic Library，且只支持真机运行，不支持模拟器

说明：本文档中涉及编译器的指引及示例图参考 Xcode 13.4 版本。



## 快速开始

1. 克隆或下载 Demo 工程源文件到本地。
2. 前往火[山引擎手机产品文档中心](https://www.volcengine.com/docs/6394/75741)下载云手机 iOS 客户端 SDK 文件。解压后将 vePhoneSDK 文件夹拷贝到Demo 工程的 VePhoneDemo 目录下。 
3. 执行 pod install 指令，成功之后，打开 VePhonePublicDemo.xcworkspace。
4. 相关的运行信息，在打印的 log 中查看。

## 接入的流程

1. 建议在 AppDelegate 的 didFinishLaunchingWithOptions 中初始化 VePhoneSDK 配置信息。

   ```objective-c
   [[VePhoneManager sharedInstance] initWithAccountId:@"------AccountID------"];。
   ```

2. 在 VePhoneViewController 中填写游戏的 ak、sk、token 等鉴权信息以及 userId、productId、podId 等配置信息。

   ```objective-c
   self.akTextField.text = @"------ak------";
   self.skTextField.text = @"------sk------";
   self.tokenTextField.text = @"------token------";
   self.userIdTextField.text = @"------userId------";
   self.productIdTextField.text = @"------productId------";
   self.rotationTextField.text = @"0";//默认为0
   self.podIdTextField.text = @"------podId------"; 
   ```

3. 然后调用 `- (void)startWithConfig:(VePhoneConfigObject *)configObj` 接口启动游戏。

   ```objective-c
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
   ```
4. 实现相关代理接口。

   ```objective-c
   #pragma mark - VePhoneManagerDelegate
   - (void)phoneManager:(VePhoneManager *)manager startSucceedResult:(NSInteger)streamProfileId reservedId:(NSString *)reservedId extra:(NSDictionary *)extra
   {
       // 启动成功，收到首帧画面回调
   }
   
   - (void)phoneManager:(VePhoneManager *)manager changedDeviceRotation:(NSInteger)rotation
   {
       // 横竖屏方向回调，注意：VePhoneSDK只负责横竖屏方向回调，不负责横竖屏的旋转，接入方根据rotation自行处理
   }
   
   - (void)phoneManager:(VePhoneManager *)manager onWarning:(VePhoneWarningCode)warnCode
   {
       // 警告回调
   }
   
   - (void)phoneManager:(VePhoneManager *)manager onError:(VePhoneErrorCode)errCode
   {
       // 错误回调
   }
   ```

5. 结束时，调用 `- (void)stop` 接口结束游戏。

   ```objective-c
   [[VePhoneManager sharedInstance] stop];
   ```

## 参考资料

客户端 SDK 下载：https://www.volcengine.com/docs/6394/75741

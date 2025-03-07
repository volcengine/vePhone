#pragma once
#include <cstdint>
#include <vector>
#include <string>


namespace vecommon {

#pragma warning(disable : 4200)
#pragma pack(push)
#pragma pack(1)

/**
 * @locale zh
 * @type keytype
 * @brief 视频渲染模式
 */
enum class VideoRenderMode {
    COVER = 1,         // 等比缩放，拉流画面短边撑满窗口，长边裁切
    FIT = 2,           // 等比缩放，居中展示完整拉流画面
    FILL = 3,          // 非等比缩放，拉伸模式，拉流画面无论长边短边均撑满窗口
};

/**
 * @locale zh
 * @type keytype
 * @brief 视频旋转角度
 */
enum class VideoRotation {
    R0 = 0,              // 顺时针旋转 0 度
    R90 = 90,            // 顺时针旋转 90 度
    R180 = 180,          // 顺时针旋转 180 度
    R270 = 270           // 顺时针旋转 270 度
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 视频编解码格式
 */
enum class VideoPixelFormat {
    RGBA = 1,
    I420,
    NV12,
    NV21,
    D3D11
};

/**
 * @locale zh
 * @type keytype
 * @brief 触控类型
 * @note 参考安卓MotionEvent{https://developer.android.com/reference/android/view/MotionEvent#ACTION_DOWN}
 */
enum class TouchType {
    None = -1,          // 默认值
    Down = 0,           // 手指按下
    Up = 1,             // 手指抬起
    Move = 2,           // 手指移动
    Cancel = 3,         // 事件关闭
    Outside = 4,        // 暂不使用
    PointerDown = 5,    // 暂不使用
    PointerUp = 6       // 暂不使用
};

/**
 * @locale zh
 * @type keytype
 * @brief 输入法消息发送类型
 */
enum class ImeCompositionType {
    Begin,
    End,
    Input,
};

/**
 * @locale zh
 * @type keytype
 * @brief 网络质量状态
 */
enum class NetworkQualityState {
    Unknown = 0,
    Excellent,
    Good,
    Poor,
    Bad,
    VeryBad,
    Down
};

/**
 * @locale zh
 * @type keytype
 * @brief 媒体流连接状态
 */
enum class StreamConnectionState {
    Disconnected = 1,       // 连接断开，断网 12s 触发，内部自动重连
    Connecting,             // 首次请求建立连接，正在连接中
    Connected,              // 首次连接成功
    Reconnecting,           // 首次连接时，10秒连接不成功；或连接成功后，断连 10 秒，自动重连中
    Reconnected,            // 连接断开后，重连成功
    Lost,                   // 处于 `DISCONNECTED` 状态超过 10 秒，且期间重连未成功
    Failed                  // 服务端异常状态导致失败，不会自动重试，可联系技术支持
};

/**
 * @locale zh
 * @type keytype
 * @brief 消息通道连接状态
 */
enum class MessageChannelState {
    Unknown = 0,
    Connected = 1,
    Disconnected = 2,
};

/**
 * @locale zh
 * @type keytype
 * @brief 云机应用前后台切换类型
 */
enum class RemoteGameSwitchType {
    None = -1,
    ClientSwitch = 0,
    RemoteAutoSwitch,
    RepeatedlyGoFront
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 本地相机ID
 */
enum class CameraId {
    Front = 0,
    Back = 1,
    External = 2,
    Invalid = 3
};

/**
 * @locale zh
 * @type keytype
 * @brief 本地渲染画布旋转角度
 */
enum class RotateDegree {
    DEGREE_0 = 0,               // ↑
    DEGREE_90 = 90,             // →
    DEGREE_180 = 180,           // ↓
    DEGREE_270 = 270            // ←
};

/**
 * @locale zh
 * @type keytype
 * @brief 会话状态
 */
enum class SessionStatus {
    Idle = 0x0000,
    Starting = 0x0001,
    Started = 0x0002,
    Streaming = 0x0003,
    Error = 0x0004,
    Stop = 0x005
};

/**
 * @locale zh
 * @type keytype
 * @brief 云机同步任务状态
 */
enum class EventSyncStatus {
    Idle = 0,
    Starting = 1,
    Started = 2,
    Stopping = 3,
    Error = 4
};

/**
 * @locale zh
 * @type keytype
 * @brief 外部渲染视频帧编码格式
 */
enum FrameFormat {
    YUVI420,    // YUV I420 格式
    ARGB,       // ARGB 格式, 字节序为 A8 R8 G8 B8
    RGBA,       // RGBA 格式, 字节序为 R8 G8 B8 A8
    BGRA        // BGRA 格式, 字节序为 B8 G8 R8 A8
};

/**
 * @locale zh
 * @type keytype
 * @brief 媒体流类型
 */
enum class StreamType {
    NONE = 0,   // 不订阅音视频流
    AUDIO = 1,  // 仅订阅音频流
    VIDEO = 2,  // 仅订阅频频流
    BOTH = 3    // 订阅音视频流
};

/**
 * @locale zh
 * @type keytype
 * @brief 旋转模式
 */
enum class RotationMode {
    AUTO_ROTATION = 0,
    PORTRAIT = 1
};

/**
 * @locale zh
 * @type keytype
 * @brief 音频注入命令
 */
enum class AudioInjectionCmd {
    STOP = 0,   // 停止音频注入
    START = 1   // 开始音频注入
};

/**
 * @locale zh
 * @type keytype
 * @brief 键盘类型
 */
enum class KeyboardType {
    POD = 0,    // 使用云端键盘
    LOCAL = 1   // 使用本地键盘
};

/**
 * @locale zh
 * @type keytype
 * @brief 快捷键类型
 */
enum class HotKey {
    CTRL_C = 0,   // 复制
    CTRL_X = 1,   // 剪切
    CTRL_A = 2    // 全选
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 特性类型
 */
enum class Feature {
    WALLPAPER = 0 // 壁纸流
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 批量拉流接口类型
 */
enum class BCVAPI {
    BATCH_POD_START = 0,
    START = 1,
    STOP = 2,
};

/**
 * @locale zh
 * @type keytype
 * @brief 会话配置
 */
struct SessionConfig {
    void* canvas{ nullptr };                        // 拉流后显示画面的画布，Windows 平台下传窗口句柄（HWND）
    int         autoRecycleTime{ 0 };               // 设置用户无操作自动回收时长
    int         videoStreamProfileId{ 0 };          // 视频流清晰度 ID
    const char* userId{ nullptr };
    const char* accountId{ nullptr };
    const char* ak{ nullptr };                      // 用户鉴权临时 access key
    const char* sk{ nullptr };                      // 用户鉴权临时 secret key
    const char* token{ nullptr };                   // 用户鉴权临时 token
    const char* userTag{ nullptr };                 // 用户标签
    const char* configurationCode{ nullptr };       // 火山侧套餐 ID
    const char* dc{ nullptr };                      // 机房ID
    const char* extra{ nullptr };                   // 客户扩展参数，只透传不消费:
    const char* debugConfig{ nullptr };             // debug配置
    bool externalRender{ false };                   // 是否需要外部渲染
    FrameFormat externalRenderFormat;               // 外部渲染视频帧格式
};

/**
 * @locale zh
 * @type keytype
 * @brief 云手机会话配置
 */
struct PhoneSessionConfig {
    SessionConfig basicConfig;
    const char* podId{ nullptr };                   // pod ID
    const char* productId{ nullptr };               // 实例所归属的业务 ID
    const char* roundId{ nullptr };                 // 本次生命周期标识符
    const char* appId{ nullptr };                   // 指定启动的应用 ID
    const char* planId{ nullptr };                  // 火山侧套餐 ID
    bool        enableScreenLock{ false };          // 是否锁定屏幕横竖屏显示
    bool        enableLocalKeyboard{ true };        // 是否开启本地键盘输入
    bool        reset{ false };                     // 退出后，是否还原Pod
    bool        muteAudio{ false };                 // 是否默认关闭音频拉流，群控场景下建议关闭
    StreamType  streamType{ StreamType::BOTH };     // 加房时自动订阅流的类型
    VideoRenderMode  renderMode{ VideoRenderMode::FIT }; // 视频的渲染模式
    float       latitude{ 0.00F };                  // 模拟定位纬度
    float       longitude{ 0.00F };                 // 模拟定位经度
    int remoteWindowWidth{ -1 };                    // Pod推流有效宽度
    int remoteWindowHeight{ -1 };                   // Pod推流有效高度
    RotationMode rotationMode{ RotationMode::AUTO_ROTATION };   // 旋转模式
    int         waitTime{ 10 };                     // 云端实例加房后等待SDK加房的时间，单位：秒，默认10秒，最短10秒，最长72小时
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 云游戏会话配置
 */
struct GameSessionConfig {
    SessionConfig basicConfig;
    const char* gameId{ nullptr };                  // 游戏 id
    const char* custom_game_id{ nullptr };          // 自定义游戏 id，与 game_id 二选一
    const char* round_id{ nullptr };                // 本次生命周期标识符
    const char* reservedId{ nullptr };              // 资源预锁定 id
    const char* planId{ nullptr };                  // 火山侧套餐 ID
    const char* profilePathList{ nullptr };         // 保存用户游戏配置文件的路径列表
    bool        enableScreenLock{ false };          // 是否锁定屏幕横竖屏显示
    bool        enableLocalKeyboard{ true };        // 是否开户本地键盘输入
};

/**
 * @locale zh
 * @type keytype
 * @brief 云机同步任务配置
 */
struct EventSyncConfig {
    const char* ak{ nullptr };                      // 用户鉴权临时access key
    const char* sk{ nullptr };                      // 用户鉴权临时secret key
    const char* token{ nullptr };                   // 用户鉴权临时token
    const char* productId{ nullptr };               // 云机所归属的业务ID
    const char* roundId{ nullptr };                 // 本次生命周期标识符
    const char* userId{ nullptr };                  // 用户ID，注：需要和SessionConfig或者BatchPodStart请求中传入的userId保持一致
    std::vector<std::string> controlledPodIdList;   // 被控云机ID列表
    bool enableForce{ true };                       // 是否强制开指令同步任务
    bool enableMulti{ false };                      // 是否支持加入多个群控房间
    const char* softwareVersion{ nullptr };         // 支持切换主控的镜像版本，可以通过ListPod获取
    const char* debugConfig{ nullptr };             // debug配置
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 云机支持特性的配置信息
 */
struct SupportFeatureConfig {
    const char* ak{ nullptr };                      // 用户鉴权临时access key
    const char* sk{ nullptr };                      // 用户鉴权临时secret key
    const char* token{ nullptr };                   // 用户鉴权临时token
    const char* productId{ nullptr };               // 云机所归属的业务ID
    std::vector<std::string> podIdList;             // 云机ID列表
    Feature feature{ Feature::WALLPAPER };          // 重要特性
    const char* debugConfig{ nullptr };             // debug配置
};

/**
 * @locale zh
 * @type keytype
 * @brief 键盘事件消息体
 */
struct KeyboardData {
    uint8_t key{ 0 };               // 键盘按键 key，非 VK_PROCESSKEY 等处理后的值，需要填入正在输入的按键值，参考 https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
    uint8_t down{ 0 };              // 键盘按键状态   0 up, 1 down
    uint8_t processed{ 0 };         // key 的值是否经过处理，如果 key 的值为 VK_PROCESSKEY，需要还原 key 的原始键值，并设置 process 为 ture
};

/**
 * @locale zh
 * @type keytype
 * @brief 鼠标点击事件消息体
 */
struct MouseKeyData {
    uint8_t key{ 0 };               // 鼠标按键 key code，参考 https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
    uint8_t down{ 0 };              // 鼠标按键状态   0 up, 1 down
    int32_t abs_x{ 0 };             // 鼠标在画面的 x 轴坐标，左-->右 映射到 [0,65535]
    int32_t abs_y{ 0 };             // 鼠标在画面的 y 轴坐标，上-->下 映射到 [0,65535]
    int32_t point_id{ 0 };          // 多点触控ID，单点情况下默认0
};

/**
 * @locale zh
 * @type keytype
 * @brief 鼠标移动事件消息体
 */
struct MouseMoveData {
    int32_t abs_x{ 0 };             // 鼠标在画面的 x 轴坐标，左-->右 映射到 [0,65535]
    int32_t abs_y{ 0 };             // 鼠标在画面的 y 轴坐标，上-->下 映射到 [0,65535]
    int32_t delta_x{ 0 };           // 相对上次鼠标位置 x 方向移动值，左负，右正
    int32_t delta_y{ 0 };           // 相对上次鼠标位置 y 方向移动值，上负，下正
    int32_t point_id{ 0 };          // 多点触控ID，单点情况下默认0
};

/**
 * @locale zh
 * @type keytype
 * @brief 鼠标滚轮事件消息体
 */
struct MouseWheelData {
    int16_t wheel{ 0 };             // 鼠标滚轮竖向滚动值
    int16_t hwheel{ 0 };            // 鼠标滚轮横向滚动值
    int32_t abs_x{ 0 };             // 鼠标在画面的 x 轴坐标，左-->右 映射到 [0,65535]
    int32_t abs_y{ 0 };             // 鼠标在画面的 y 轴坐标，上-->下 映射到 [0,65535]
};

/**
 * @locale zh
 * @type keytype
 * @brief 鼠标滚轮事件消息体(ARM)
 */
struct MouseWheelDataArm {
    double  x{ 0 };                  // 鼠标滚轮竖向滚动值，映射到 [0,65535]
    double  y{ 0 };                  // 鼠标滚轮横向滚动值，映射到 [0,65535]
    double  axis_v{ 0 };             // 表示上下方向，-1.0 下 1.0 上
    double  axis_h{ 0 };             // 表示左右方向，-1.0 右 1.0 左
    int16_t action{ -1 };            // 动作类型，如0-ACTION_DOWN, 1-ACTION_UP, 2-ACTION_MOVE 8-ACTION_SCROLL
    int16_t button{ -1 };            // 0:左键， 1:右键， 2:中键
    int32_t point_id{ 0 };           // 多点触控ID，单点情况下默认0
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 手柄事件消息体
 */
struct GamepadInputData {
    uint8_t index{ 0 };             // 手柄索引值
    int32_t buttons{ 0 };           // 手柄按键值，参数 msdn XINPUT_GAMEPAD 结构 https://docs.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_gamepad
    uint8_t lt{ 0 };                // left trigger，范围 [0, 256)
    uint8_t rt{ 0 };                // right trigger，范围 [0, 256)
    int16_t lx{ 0 };                // left thumbstick x，范围 [-32768, 32768)
    int16_t ly{ 0 };                // left thumbstick y，范围 [-32768, 32768)
    int16_t rx{ 0 };                // right thumbstick x，范围 [-32768, 32768)
    int16_t ry{ 0 };                // right thumbstick y，范围 [-32768, 32768)
};

/**
 * @locale zh
 * @type keytype
 * @brief 触控事件消息体
 */
struct TouchData {
    int16_t     index{ 0 };                     // 触屏手指索引值
    TouchType   type{ TouchType::None };        // 触屏类型
    int32_t     abs_x{ 0 };                     // 触屏点在画面的 x 轴坐标，左-->右 映射到 [0,65535]
    int32_t     abs_y{ 0 };                     // 触屏点在画面的 y 轴坐标，上-->下 映射到 [0,65535]
};

/**
 * @locale zh
 * @type keytype
 * @brief 多指触控消息体
 */
struct TouchArrayData {
    uint8_t     count{ 0 };         // 触屏手指数
    TouchData   touch[0];
};

/**
 * @locale zh
 * @type keytype
 * @brief 多指触控消息体(优化)
 */
struct MulitTouchData {
    int32_t x{ 0 };                    // 事件X坐标位置 左-->右 映射到 [0,65535]
    int32_t y{ 0 };                    // 事件Y坐标位置 上-->下 映射到 [0,65535]
    int32_t point_id{ -1 };            // 触摸点ID
    int32_t touch_action{ -1 };        // 参考{@link#TouchType}定义
};

/**
 * @locale zh
 * @type keytype
 * @brief 输入法事件消息体
 */
struct ImeCompositionData {
    ImeCompositionType  type;            // 输入类型
    const char* str;                     // 字符串，utf8 格式
    int32_t             len{ 0 };        // 输入长度
    int32_t             start{ 0 };      // 输入起点
    int32_t             end{ 0 };        // 输入结束点
};

/**
 * @locale zh
 * @type keytype
 * @brief 输入法状态消息体
 */
struct ImeStateData {
    bool    enable{ false };        // 输入法状态，true 为开启，false 为关闭
    int32_t w{ 0 };                 // 窗口客户区宽
    int32_t h{ 0 };                 // 窗口客户区高
    int32_t x{ 0 };                 // IME 窗口坐标 x，输入框左上角
    int32_t y{ 0 };                 // IME 窗口坐标 y，输入框左上角
    int32_t fw{ 0 };                // 字体宽（平均，差不多就行）
    int32_t fh{ 0 };                // 字体高
};

/**
 * @locale zh
 * @type keytype
 * @brief 鼠标光标位置消息体
 */
struct MouseCursorPos {
    int32_t abs_x{ 0 };             // 鼠标在画面的 x 轴坐标，左-->右 映射到 [0,65535]
    int32_t abs_y{ 0 };             // 鼠标在画面的 y 轴坐标，上-->下 映射到 [0,65535]
};

/**
 * @locale zh
 * @type keytype
 * @brief 手柄震动事件消息体
 */
struct GamepadVibrationData {
    uint8_t index{ 0 };             // 手柄索引值
    int32_t lm{ 0 };                // 左马达，参考 https://docs.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_vibration
    int32_t rm{ 0 };                // 右马达
};

/**
 * @locale zh
 * @type keytype
 * @brief 音频统计信息
 */
struct AudioStats {
    float   audio_loss_rate{ 0 };           // 音频丢包率。统计周期内的音频下行丢包率，取值范围为 [0, 1]
    int     received_kbitrate{ 0 };         // 接收码率。统计周期内的音频接收码率，单位为 kbps
    int     stall_count{ 0 };               // 音频卡顿次数。统计周期内的卡顿次数
    int     stall_duration{ 0 };            // 音频卡顿时长。统计周期内的卡顿时长，单位为 ms
    long    e2e_delay{ 0 };                 // 用户体验级别的端到端延时。从发送端采集完成编码开始到接收端解码完成渲染开始的延时，单位为 ms
    int     playout_sample_rate{ 0 };       // 播放采样率。统计周期内的音频播放采样率信息，单位为 Hz
    int     stats_interval{ 0 };            // 统计间隔。此次统计周期的间隔，单位为 ms
    int     rtt{ 0 };                       // 客户端到服务端数据传输的往返时延，单位为 ms
    int     total_rtt{ 0 };                 // 发送端——服务端——接收端全链路数据传输往返时延。单位为 ms
    int     quality{ 0 };                   // 云端用户发送的音频流质量
    int     jitter_buffer_delay{ 0 };       // 因引入 jitter buffer 机制导致的延时。单位为 ms
    int     num_channels{ 0 };              // 音频声道数
    int     received_sample_rate{ 0 };      // 音频接收采样率。统计周期内接收到的云端音频采样率信息，单位为 Hz
    int     frozen_rate{ 0 };               // 云端用户在加入房间后发生音频卡顿的累计时长占音频总有效时长的百分比。音频有效时长是指云端用户进房发布音频流后，除停止发送音频流和禁用音频模块之外的音频时长
    int     concealed_samples{ 0 };         // 音频丢包补偿(PLC) 样点总个数
    int     concealment_event{ 0 };         // 音频丢包补偿(PLC) 累计次数
    int     dec_sample_rate{ 0 };           // 音频解码采样率。统计周期内的音频解码采样率信息，单位为 Hz
    int     dec_duration{ 0 };              // 解码时长。对此次统计周期内接收的云端音频流进行解码的总耗时，单位为 s
    int     jitter{ 0 };                    // 音频下行网络抖动，单位为 ms
};

/**
 * @locale zh
 * @type keytype
 * @brief 视频统计信息
 */
struct VideoStats {
    uint8_t clarity{ 0 };                       // 清晰度 id
    int32_t width{ 0 };                         // 视频宽度
    int32_t height{ 0 };                        // 视频高度
    float   video_loss_rate{ 0 };               // 视频丢包率。统计周期内的视频下行丢包率，单位为 % ，取值范围：[0，1]
    int32_t received_kbitrate{ 0 };             // 接收码率。统计周期内的视频接收码率，单位为 kbps
    int32_t decoder_output_frame_rate{ 0 };     // 解码器输出帧率。统计周期内的视频解码器输出帧率，单位 fps
    int32_t renderer_output_frame_rate{ 0 };    // 渲染帧率。统计周期内的视频渲染帧率，单位 fps
    int32_t stall_count{ 0 };                   // 卡顿次数。统计周期内的卡顿次数
    int32_t stall_duration{ 0 };                // 卡顿时长。统计周期内的视频卡顿总时长。单位 ms
    int64_t e2e_delay{ 0 };                     // 用户体验级别的端到端延时。从发送端采集完成编码开始到接收端解码完成渲染开始的延时，单位为 ms
    bool    is_screen{ false };                 // 所属用户的媒体流是否为屏幕流。你可以知道当前数据来自主流还是屏幕流
    int32_t stats_interval{ 0 };                // 统计间隔，此次统计周期的间隔，单位为 ms，此字段用于设置回调的统计周期，目前设置为 2s
    int32_t rtt{ 0 };                           // 往返时延，单位为 ms
    int32_t frozen_rate{ 0 };                   // 云端用户在进房后发生视频卡顿的累计时长占视频总有效时长的百分比（%）。视频有效时长是指云端用户进房发布视频流后，除停止发送视频流和禁用视频模块之外的视频时长
    int32_t video_index{ 0 };                   // 对应多种分辨率的流的下标
    int32_t jitter{ 0 };                        // 视频下行网络抖动，单位为 ms
};

/**
 * @locale zh
 * @type keytype
 * @brief 视频帧信息
 */
struct VideoFrameInfo {
    int32_t         width{ 0 };                     // 视频帧宽（像素）
    int32_t         height{ 0 };                    // 视频帧高（像素）
    VideoRotation   rotation{ VideoRotation::R0 };  // 视频帧顺时针旋转角度
};

/**
 * @locale zh
 * @type keytype
 * @brief 视频流的配置信息
 */
struct ControlVideoConfig {
    void* canvas{ nullptr };                        // 拉流后显示画面的画布，Windows 平台下传窗口句柄（HWND）
    std::string podId;                              // pod ID
    bool autoSubscribe{ true };                     // 是否自动订阅
};

/**
 * @locale zh
 * @type keytype
 * @brief 批量拉流控制配置信息
 */
struct BatchControlVideoConfig {
    std::vector<ControlVideoConfig> videoConfigs;   // 指定要拉流的pod及其对应的渲染画布
    const char* batchPodStartResult{ nullptr };     // 由外部传入batchPodStart的接口返回结果，若不为空指针则会跳过内部对应网络请求。
    const char* productId{ nullptr };               // 实例所归属的业务 ID
    const char* roundId{ nullptr };                 // 本次生命周期标识符
    const char* userId{ nullptr };
    const char* accountId{ nullptr };
    const char* ak{ nullptr };                      // 用户鉴权临时 access key
    const char* sk{ nullptr };                      // 用户鉴权临时 secret key
    const char* token{ nullptr };                   // 用户鉴权临时 token
    const char* debugConfig{ nullptr };             // debug配置
    bool externalRender{ false };                   // 是否需要外部渲染
    FrameFormat externalRenderFormat{ FrameFormat::ARGB };             // 外部渲染视频帧格式
    int         videoStreamProfileId{ 0 };          // 视频流清晰度 ID
    int         waitTime{ 10 };                     // 云端实例加房后等待SDK加房的时间，单位：秒，默认10秒，最短10秒，最长72小时
    int autoRecycleTime{ 0 };
};

/**
 * @locale zh
 * @type keytype
 * @brief BatchPodStart请求失败的Pod信息
 */
struct PodError {
    const char* podId;
    const char* errorMessage;
    int errorCode;
};

/**
 * @locale zh
 * @type keytype
 * @brief BatchPodStart请求成功的Pod信息
 */
struct PodInfo {
    const char* podId;
};

/**
 * @hidden
 * @locale zh
 * @type keytype
 * @brief 云机同步房间信息
 */
struct EventSyncRoomInfo {
    std::string userId;
    std::string roomId;
    std::string appId;
    std::string token;
    int roomSize;
};

/**
 * @locale zh
 * @type keytype
 * @brief 云机操控权状态
 */
struct ControlState {
    std::string userId;     // 目标用户ID
    bool enable{ false };   // 目标用户是否具有操控权
};

struct ChannelMessage {
    int type;
    std::string msgId;
    std::string ackId;
    std::string sourceUid;
    std::string destUid;
    std::string payload;
    int64_t timestamp;
};

#pragma pack(pop)

} // namespace vecommon

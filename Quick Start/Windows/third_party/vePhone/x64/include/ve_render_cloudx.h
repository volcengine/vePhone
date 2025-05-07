#pragma once
#include "ve_type_defines.h"
#include "ve_session_listener.h"
#include "ve_common.h"
#include "ve_phone_session.h"
#include "ve_batch_control_video.h"
#include "ve_eventsync_listener.h"
#include "ve_support_feature_listener.h"


namespace vecommon {

/**
 * @locale zh
 * @type api
 * @brief 火山云渲染引擎类
 * @note 获取云渲染引擎实例：VeCloudRenderX* veCloudRenderX = vecommon::CreateVeCloudRenderX();
 */
class VeCloudRenderX {

public:

    /**
     * @locale zh
     * @brief 初始化VeCloudRenderX实例
     * @param accountId 账户ID
     * @param roomPerEngine 每个引擎创建的房间数量，默认10个
     * @return true：调用成功，false：调用失败
     * @note 使用VeCloudRenderX能力之前，必须调用此api进行初始化
     */
    virtual bool prepare(const std::string& accountId, int roomPerEngine = 10) = 0;

    /**
     * @locale zh
     * @brief 设置是否开启调试模式
     * @param debug true：开启，false：关闭
     * @param logDir 日志生成的位置
     */
    virtual void setDebug(bool debug, const char* logDir) = 0;

    /**
     * @locale zh
     * @brief 获取设备ID
     * @return 设备ID
     */
    virtual const char* getDeviceId() = 0;

    /**
     * @locale zh
     * @brief 获取SDK版本号
     * @return SDK版本号
     */
    virtual const char* getSDKVersion() = 0;

    /**
     * @locale zh
     * @brief 创建云手机会话实例
     * @param config 云手机会话配置信息
     * @param listener 云手机会话监听器
     * @return 云手机会话实例
     */
    virtual PhoneSession* createPhoneSession(const PhoneSessionConfig& config, ISessionListener* listener) = 0;

    /**
     * @locale zh
     * @brief 创建批量拉流控制实例
     * @param config 批量拉流控制配置信息
     * @return 批量拉流控制实例
     */
    virtual BatchControlVideo* createBatchControlVideo(const BatchControlVideoConfig& config) = 0;

    /**
     * @locale zh
     * @brief 开始云机同步任务
     * @param config 云机同步配置信息
     * @param listener 云机同步监听器
     * @return true：调用成功 false：调用失败
     */
    virtual bool startEventSync(const EventSyncConfig& config, IEventSyncListener* listener) = 0;

     /**
      * @locale zh
      * @brief 停止云机同步任务
      * @return true：调用成功 false：调用失败
      */
    virtual bool stopEventSync() = 0;

    /**
     * @locale zh
     * @brief 设置云机同步监听器
     * @param listener 监听器
     */
    virtual void setEventSyncListener(IEventSyncListener* listener) = 0;

    /**
     * @locale zh
     * @brief 获取云机同步状态
     * @return 云机同步状态
     */
    virtual vecommon::EventSyncStatus getEventSyncStatus() = 0;

    /**
     * @locale zh
     * @brief 设置主控Session
     * @param session 云手机会话实例
     * @return true：调用成功 false：调用失败
     */
    virtual bool setMasterSession(PhoneSession* session) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 检查云机是否支持某个特性
     * @param config 云机支持特性的配置信息
     * @param listener 云机支持特性的监听器
     * @return true：调用成功 false：调用失败
     */
    virtual bool checkIfSupportFeature(const SupportFeatureConfig& config, ISupportFeatureListener* listener) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 设置云机支持特性的监听器
     * @param listener 监听器
     */
    virtual void setSupportFeatureListener(ISupportFeatureListener* listener) = 0;

};

extern "C" {

    /**
     * @locale zh
     * @type api
     * @brief 创建VeCloudRenderX实例
     */
    NATIVESDK_API VeCloudRenderX* CreateVeCloudRenderX();

    /**
     * @locale zh
     * @type api
     * @brief 销毁VeCloudRenderX实例
     */
    NATIVESDK_API void DestroyVeCloudRenderX();

    /**
     * @locale zh
     * @type api
     * @brief 停止云手机会话
     * @param session 云手机会话实例
     */
    NATIVESDK_API void ExternalStopSession(PhoneSession* session);
}

} // namespace vecommon
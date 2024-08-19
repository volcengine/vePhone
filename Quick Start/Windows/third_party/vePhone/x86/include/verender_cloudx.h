#pragma once

#include "ve_type_defines.h"
#include "ve_session_listener.h"
#include "ve_common.h"
#include "vephone_session.h"
#include "ve_batch_control_video.h"
#include "ve_eventsync_listener.h"
#include "ve_support_feature_listener.h"

/**
 * @type api
 * @brief 云渲染引擎
 *      以单例形式提供
 *
 * @note 获取云渲染引擎实例 #CreateVeCloudRenderX()
 *
 */
namespace vecommon {

class VeCloudRenderX {

public:

    /**
     * @type api
     * @brief 准备VeRender SDK Engine
     * @param [in] roomPerEngine 每个引擎创建的房间数量，默认10个
     * @note 使用VeRenderEngine能力之前，必须调用此api进行初始化.
     */
    virtual bool prepare(int roomPerEngine = 10) = 0;

    /**
     * @type api
     * @brief 创建一次云渲染，获取Session对象
     * @param [in] config 启动配置信息
     * @param [in] listener session相关回调
     */
    virtual PhoneSession* createPhoneSession(const PhoneSessionConfig& config, ISessionListener* listener) = 0;

    /**
     * @type api
     * @brief 是否设置调试模式
     */
    virtual void setDebug(bool debug, const char* logDir) = 0;

    /**
     * @type api
     * @brief 获取设备ID
     */
    virtual const char* getDeviceId() = 0;

    /**
     * @type api
     * @brief 获取SDK版本号
     */
    virtual const char* getSDKVersion() = 0;


    /**
     * @type api
     * @brief 创建群控小流视频对象
     * @param [in] config 启动配置信息
     */
    virtual BatchControlVideo* createBatchControlVideo(const BatchControlVideoConfig& config) = 0;

    /**
     * @type api
     * @brief 开始云机指令同步任务
     * @param [in] config 指令同步配置信息
     *        [in] listener 指令同步监听器
     * @return true: 调用成功 false: 调用失败
     */
    virtual bool startEventSync(const EventSyncConfig& config, IEventSyncListener* listener) = 0;

    /**
     * @type api
     * @brief 停止云机指令同步任务
     * @return true: 调用成功 false: 调用失败
     */
    virtual bool stopEventSync() = 0;

    /**
     * @type api
     * @brief 设置云机指令同步任务的监听器
     */
    virtual void setEventSyncListener(IEventSyncListener* listener) = 0;

    /**
     * @type api
     * @brief 获取云机指令同步状态
     */
    virtual vecommon::EventSyncStatus getEventSyncStatus() = 0;

    /**
     * @type api
     * @brief 设置主控Session
     * @return true: 设置成功 false: 设置失败
     */
    virtual bool setMasterSession(PhoneSession* session) = 0;

    /**
     * @type api
     * @brief 云机是否均支持某个特性
     * @return true: 调用成功 false: 调用失败
     */
    virtual bool checkIfSupportFeature(const SupportFeatureConfig& config, ISupportFeatureListener* listener) = 0;

    /**
     * @type api
     * @brief 设置云机支持特性的监听器
     */
    virtual void setSupportFeatureListener(ISupportFeatureListener* listener) = 0;

};

extern "C" {

    /**
     * @type api
     * @brief 创建VeCloudRenderX实例
     * @note [sample code] VeCloudRenderX* veCloudRenderX = vecommon::CreateVeCloudRenderX();
     */
    NATIVESDK_API VeCloudRenderX* CreateVeCloudRenderX();

    /**
     * @type api
     * @brief 销毁VeCloudRenderX实例
     * @note [sample code] vecommon::DestroyVeCloudRenderX();
     */
    NATIVESDK_API void DestroyVeCloudRenderX();

    /**
     * @type api
     * @brief 停止会话
     */
    NATIVESDK_API void ExternalStopSession(PhoneSession* session);
}

} // namespace vecommon
#pragma once
#include "ve_type_defines.h"

class BatchControlListener
{
public:

    /**
     * @type callback
     * @brief BatchPodStart成功
     * @param [in] code, 状态码  <br>
     * @param [in] msg, 错误信息  <br>
     */
    virtual void onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* pod_list, const std::vector<vecommon::PodError>* pod_errors) {
        // 1. 请求成功，调用bcv.start接口
    }

    /**
     * @type callback
     * @brief start成功回调
     */
    virtual void onStartSuccess(const char* pod_id) {
    }

    /**
     * @type callback
     * @brief 远端用户加房回调
     *        - 根据对应的pod窗口是否对用户可见，来决定是否进行订阅操作
     *        - Warning: 可能会增加首帧耗时
     * @param [in] pod_id，对端podId  <br>
     */
    virtual void onPodJoin(const char* pod_id) {
        (void)pod_id;
    }

    /**
     * @type callback
     * @brief 启动成功
     * @param [in] pod_id, 对端podId  <br>
     * @param [in] video_stream_profile, 清晰度档位  <br>
     */
    virtual void onFirstVideoFrameArrived(const char* pod_id, int video_stream_profile) {
        (void)pod_id;
        (void)video_stream_profile;
    }

    /**
     * @type callback
     * @brief 云手机停止回调
     * @param [in] pod_id, 对端podId  <br>
     */
    virtual void onStop(const char* pod_id) {
        (void)pod_id;
    }


    /**
     * @type callback
     * @brief SDK内部产生的错误回调
     * @param [in] user_id, 远端用户ID  <br>
     * @param [in] code，参考开发者文档
     * @param [in] msg，错误信息
     */
    virtual void onError(const char* pod_id, int code, const char* msg) {
        (void)pod_id;
        (void)code;
        (void)msg;
    }

    /**
     * @type callback
     * @brief SDK内部产生的警告回调
     * @param [in] user_id, 远端用户ID  <br>
     * @param [in] code，参考开发者文档
     * @param [in] msg，错误信息
     */
    virtual void onWarning(const char* pod_id, int code, const char* msg) {
        (void)pod_id;
        (void)code;
    }

};
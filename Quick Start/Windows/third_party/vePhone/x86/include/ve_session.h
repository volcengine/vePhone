#pragma once
#include "ve_type_defines.h"
#include "ve_session_listener.h"


namespace vecommon {

/**
 * @locale zh
 * @type api
 * @brief 云渲染会话类
 */
class Session {

public:

    /**
     * @locale zh
     * @brief 析构函数
     * @hidden
     */
    virtual ~Session() = default;

    /**
     * @locale zh
     * @brief 开始会话
     */
    virtual void start() = 0;

    /**
     * @locale zh
     * @brief 停止会话
     */
    virtual void stop() = 0;

    /**
     * @locale zh
     * @brief 获取会话ID
     * @return 会话ID
     */
    virtual const char* getSessionId() = 0;

    /**
     * @locale zh
     * @brief 获取会话状态
     * @return 会话状态
     */
    virtual vecommon::SessionStatus getSessionStatus() = 0;

    /**
     * @locale zh
     * @brief 设置会话监听器，建议在调用start接口之前设置
     * @param listener 监听器
     */
    virtual void setListener(vecommon::ISessionListener* listener) = 0;

};

} // namespace vecommon
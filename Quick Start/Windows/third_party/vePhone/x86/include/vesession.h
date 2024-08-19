#pragma once

#include "ve_type_defines.h"
#include "ve_session_listener.h"

namespace vecommon {

/**
 * @type interface
 * @brief 云渲染会话接口
 */
class Session {

public:
    virtual ~Session() = default;

    /**
     * @type api
     * @brief 启动会话
     */
    virtual void start() = 0;

    /**
     * @type api
     * @brief 停止会话
     */
    virtual void stop() = 0;

    /**
     * @type api
     * @brief 获取会话 ID
     */
    virtual const char* getSessionId() = 0;

    /**
     * @type api
     * @brief 获取会话状态
     * @return 参考{@link vecommon::SessionStatus}定义
     */
    virtual vecommon::SessionStatus getSessionStatus() = 0;

    /**
     * @type api
     * @brief 设置监听回调
     * @note 通常建议在调用session start流程之前设置监听
     */
    virtual void setListener(ISessionListener* listener) = 0;

};


} // vecommon
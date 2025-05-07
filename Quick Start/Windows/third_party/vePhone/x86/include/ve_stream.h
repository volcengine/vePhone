#pragma once
#include <cstdint>

namespace vecommon {

class VeStream {

public:

    virtual ~VeStream() = default;

    // 离开群控房间
    virtual void leaveEventSyncRoom() = 0;

    // 发送房间消息，用于群控场景
    virtual void sendRoomMessageString(const char* message) = 0;
    virtual void sendRoomMessageBinary(int size, const uint8_t* message) = 0;
    virtual void sendUserMessageString(const char* message, const char* remoteUserId) = 0;
    virtual void sendUserMessageBinary(int size, const uint8_t* message, const char* remoteUserId) = 0;
};

} // namespace vecommon
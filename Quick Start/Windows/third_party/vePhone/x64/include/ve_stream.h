#pragma once
#include <cstdint>

class VeStream {
public:
    virtual ~VeStream() = default;

    // �뿪Ⱥ�ط���
    virtual void leaveEventSyncRoom() = 0;

    // ���ͷ�����Ϣ������Ⱥ�س���
    virtual void sendRoomMessageString(const char* message) = 0;
    virtual void sendRoomMessageBinary(int size, const uint8_t* message) = 0;
};
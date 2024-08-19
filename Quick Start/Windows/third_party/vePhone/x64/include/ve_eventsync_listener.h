#pragma once

#include "ve_type_defines.h"

class IEventSyncCallback {
public:
	virtual void onEventSyncRoomStateChanged(const char* roomId, int state) {
		(void)roomId;
		(void)state;
	}

	virtual void onEventSyncUserJoined(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}

	virtual void onEventSyncUserLeave(const char* userId, const char* roomId, int reason) {
		(void)userId;
		(void)roomId;
		(void)reason;
	}
};

class IEventSyncListener {
public:
	/*
	* @type callback
	* @brief Ⱥ�ع����з�������Ļص�
	* @param [in] code ������
	*		      -1 -- LIST_POD_REQUEST_FAILED
	*			  -2 -- LIST_POD_PARSE_RESPONSE_FAILED
	*			  -3 -- POD_IMAGE_NOT_SUPPORT
	*			  -4 -- EVENT_SYNC_REQUEST_FAILED
	*			  -5 -- EVENT_SYNC_PARSE_RESPONSE_FAILED
	*			  -6 -- EMPTY_RTC_APP_ID
	*			  -7 -- INVALID_ROOM_INFO
	*			else -- MASTER_JOIN_ROOM_FAILED
	* @param [in] msg ������Ϣ
	*/
	virtual void onEventSyncError(int code, const char* msg) {
	}

	/*
	* @type callback
	* @brief ����(��SDK)�ӷ��ɹ��Ļص�
	*/
	virtual void onMasterJoinRoomSuccess() {
	}

	/*
	* @type callback
	* @brief �����ƻ��ӷ��Ļص�
	* @param [in] userId �ӷ��û�Id
	* @param [in] roomId ����Id
	*/
	virtual void onContorlledUserJoined(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}

	/*
	* @type callback
	* @brief �����ƻ��뷿�Ļص�
	* @param [in] userId �ӷ��û�Id
	* @param [in] roomId ����Id
	*/
	virtual void onContorlledUserLeave(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}
};
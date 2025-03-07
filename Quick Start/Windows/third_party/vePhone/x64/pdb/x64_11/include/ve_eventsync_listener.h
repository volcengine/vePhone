#pragma once
#include "ve_type_defines.h"


namespace vecommon {

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


/**
 * @locale zh
 * @type callback
 * @brief 云机同步操作的监听器
 */
class IEventSyncListener {

public:

	/**
	 * @locale zh
	 * @brief 同步操作过程中发生错误的回调
	 * @param code 错误码
	 *			- -1：LIST_POD_REQUEST_FAILED
	 *			- -2：LIST_POD_PARSE_RESPONSE_FAILED
	 *			- -3：POD_IMAGE_NOT_SUPPORT
	 *			- -4：EVENT_SYNC_REQUEST_FAILED
	 *			- -5：EVENT_SYNC_PARSE_RESPONSE_FAILED
	 *			- -6：EMPTY_RTC_APP_ID
	 *			- -7：INVALID_ROOM_INFO
	 *			- -8：EVENT_SYNC_TIMEOUT
	 *		  - else：MASTER_JOIN_ROOM_FAILED
	 * @param msg 错误信息
	 */
	virtual void onEventSyncError(int code, const char* msg) {}

	/**
	 * @locale zh
	 * @brief 同步操作成功的回调
	 */
	virtual void onEventSyncSuccess() {}

	/**
	 * @locale zh
	 * @brief 主控(即SDK)加房成功的回调
	 */
	virtual void onMasterJoinRoomSuccess() {}

	/**
	 * @locale zh
	 * @brief 被控云机加房的回调
	 * @param userId 加房用户Id
	 * @param roomId 房间Id
	 */
	virtual void onContorlledUserJoined(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}

	/**
	 * @locale zh
	 * @brief 被控云机离房的回调
	 * @param userId 加房用户Id
	 * @param roomId 房间Id
	 */
	virtual void onContorlledUserLeave(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}
};

} // namespace vecommon
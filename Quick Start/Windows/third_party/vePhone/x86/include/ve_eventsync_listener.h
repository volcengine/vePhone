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

	virtual void onEventSyncUserTokenWillExpire(const char* userId, const char* roomId) {
		(void)userId;
		(void)roomId;
	}

	virtual void onEventSyncUserUpdateTokenResult(const char* userId, const char* roomId, int result) {
		(void)userId;
		(void)roomId;
		(void)result;
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
	 *			- -1：ERROR_LIST_POD_REQUEST_FAILED
	 *			- -2：ERROR_LIST_POD_PARSE_RESPONSE_FAILED
	 *			- -3：ERROR_POD_IMAGE_NOT_SUPPORT
	 *			- -4：ERROR_EVENT_SYNC_REQUEST_FAILED
	 *			- -5：ERROR_EVENT_SYNC_PARSE_RESPONSE_FAILED
	 *			- -6：ERROR_EMPTY_RTC_APP_ID
	 *			- -7：ERROR_INVALID_ROOM_INFO
	 *			- -8：ERROR_TOKEN_HAS_EXPIRED
	 *		  - else：ERROR_MASTER_JOIN_ROOM_FAILED
	 * @param msg 错误信息
	 * @param userId 用户Id，一般为podId
	 */
	virtual void onEventSyncError(int code, const char* msg, const char* userId = nullptr) {}

	/**
	 * @locale zh
	 * @brief 同步操作成功的回调
	 */
	virtual void onEventSyncSuccess() {}

	/**
	 * @locale zh
	 * @brief 同步操作结果的回调
	 * @param result 同步操作结果
	 * @param failureList 同步操作失败列表
	 */
	virtual void onEventSyncResult(const vecommon::EventSyncResult result,
		const std::vector<vecommon::EventSyncFailure>& failureList) {
		(void)result;
		(void)failureList;
	}

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

	/**
	 * @locale zh
	 * @brief 同步操作过程中发生警告的回调
	 * @param code 警告码
	 *				- -1：WARNING_TOKEN_WILL_EXPIRE
	 * @param msg 警告信息
	 * @param userId 用户Id，一般为podId
	 */
	virtual void onEventSyncWarning(int code, const char* msg, const char* userId) {
		(void)code;
		(void)msg;
		(void)userId;
	}

};

} // namespace vecommon
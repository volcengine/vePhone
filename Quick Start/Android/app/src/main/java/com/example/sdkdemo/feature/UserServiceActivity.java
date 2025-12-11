package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.UserService;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.List;
import java.util.Map;


/**
 * 该类用于展示与多用户服务{@link UserService}相关的功能接口的使用方法
 * 当多个用户连接同一个云端实例时，每个用户默认拥有对实例的操控权限，
 * 可以通过该服务来控制和查询每个用户对于实例的操控权限。
 */
public class UserServiceActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private UserService mUserService;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnEnableControl, mBtnHasControl, mBtnGetAllControls;
    private EditText mEtUserId;
    private CheckBox mCbEnableControl;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_user_service);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mEtUserId = findViewById(R.id.et_user_id);
        mCbEnableControl = findViewById(R.id.cb_enable_control);
        mBtnEnableControl = findViewById(R.id.btn_enable_control);
        mBtnHasControl = findViewById(R.id.btn_has_control);
        mBtnGetAllControls = findViewById(R.id.btn_get_all_controls);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnEnableControl.setOnClickListener(view -> {
            /**
             * int enableControl(String userId, boolean enable)
             * 设置指定用户是否具有云手机操控权。
             * 默认每个用户进房时都具备操控权，可以通过本接口动态关闭控制权。
             * 操作结果通过 {@link UserService.ControlListener#onEnableControlResult(int, UserService.ControlState, String)} 返回。
             *
             * @param userId 用户ID
             * @param enable true -- 开启云手机操控权
             *               false -- 关闭云手机操控权
             *
             * @return 0 -- 方法调用成功
             *        -1 -- 方法调用失败
             */
            if (mUserService != null) {
                if (mEtUserId.getText() != null && !mEtUserId.getText().toString().isEmpty()) {
                    mUserService.enableControl(mEtUserId.getText().toString(), mCbEnableControl.isChecked());
                }
            }
            else {
                Log.e(TAG, "mUserService == null");
            }
        });

        mBtnHasControl.setOnClickListener(view -> {
            /**
             * int hasControl(String userId)
             * 异步查询指定用户是否具有云手机操控权。
             * 结果通过 {@link UserService.ControlListener#onHasControlResult(int, UserService.ControlState, String)} 返回。
             *
             * @param userId 用户ID
             *
             * @return 0 -- 方法调用成功
             *        -1 -- 方法调用失败
             */
            if (mUserService != null) {
                if (mEtUserId.getText() != null && !mEtUserId.getText().toString().isEmpty()) {
                    mUserService.hasControl(mEtUserId.getText().toString());
                }
            }
            else {
                Log.e(TAG, "mUserService == null");
            }
        });


        mBtnGetAllControls.setOnClickListener(v -> {
            /**
             * int getAllControls()
             * 异步查询所有用户的操控权信息。
             * 结果通过 {@link UserService.ControlListener#onAllControlsResult(int, List, String)} 返回。
             *
             * @return 0 -- 方法调用成功
             *        -1 -- 方法调用失败
             */
            if (mUserService != null) {
                mUserService.getAllControls();
            }
            else {
                Log.e(TAG, "mUserService == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    String userId = SdkUtil.getClientUid();
                    mEtUserId.setText(userId);
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(userId)
                            .ak(auth.ak)
                            .sk(auth.sk)
                            .token(auth.token)
                            .container(mContainer)
                            .enableLocalKeyboard(true)
                            .roundId(SdkUtil.getRoundId())
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .streamListener(this);
                    VePhoneEngine.getInstance().start(builder.build(), this);
                },
                p -> {
                    showTipDialog(MessageFormat.format(getString(R.string.invalid_phone_play_config) , p));
                });
    }

    @Override
    protected void onResume() {
        super.onResume();
        VePhoneEngine.getInstance().resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VePhoneEngine.getInstance().pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mUserService = VePhoneEngine.getInstance().getUserService();
        if (mUserService != null) {
            /**
             * void setControlListener(UserService.ControlListener listener)
             * 设置用户操控权监听器
             *
             * @param listener 用户操控权监听器
             */
            mUserService.setControlListener(new UserService.ControlListener() {
                /**
                 * 当前或其他用户通过{@link UserService#enableControl(String, boolean)}调整操控权时收到该回调
                 *
                 * @param controlState 用户操控权状态
                 */
                @Override
                public void onControlStateChanged(@NonNull UserService.ControlState controlState) {
                    Log.i(TAG, "[onControlStateChanged] controlState: " + controlState);
                }

                /**
                 * 配置制定用户操控权结果回调
                 *
                 * @param code 0 -- 成功并返回操控权状态
                 *             else -- 失败错误码
                 * @param controlState 用户操控权状态
                 * @param message 提示信息
                 */
                @Override
                public void onEnableControlResult(int code, @Nullable UserService.ControlState controlState, @NonNull String message) {
                    Log.i(TAG, "[onEnableControlResult] code: " + code + ", controlState: " + controlState + ", message: " + message);
                }

                /**
                 * 查询指定用户是否具有控制权结果回调
                 *
                 * @param code 0 -- 成功并返回操控权状态
                 *             else -- 失败错误码
                 * @param controlState 用户操控权状态
                 * @param message 提示信息
                 */
                @Override
                public void onHasControlResult(int code, @Nullable UserService.ControlState controlState, @NonNull String message) {
                    Log.i(TAG, "[onEnableControlResult] code: " + code + ", controlState: " + controlState + ", message: " + message);
                }

                /**
                 * 获取全部具有操控权的用户结果回调
                 *
                 * @param code 0 -- 成功并返回操控权状态
                 *             else -- 失败错误码
                 * @param statesList 用户操控权状态
                 * @param message 提示信息
                 */
                @Override
                public void onAllControlsResult(int code, @Nullable List<UserService.ControlState> statesList, @NonNull String message) {
                    Log.i(TAG, "[onAllControlsResult] code: " + code + ", statesList: " + statesList + ", message: " + message);
                }

                /**
                 * 远端用户上线回调
                 *
                 * @param userId 用户ID
                 */
                @Override
                public void onUserJoin(String userId) {
                    Log.i(TAG, "[onUserJoin] userId: " + userId);
                }

                /**
                 * 远端用户下线回调
                 *
                 * @param userId 用户ID
                 */
                @Override
                public void onUserLeave(String userId) {
                    Log.i(TAG, "[onUserLeave] userId: " + userId);
                }
            });
        }
        else {
            Log.e(TAG, "mUserService == null");
        }
    }

}

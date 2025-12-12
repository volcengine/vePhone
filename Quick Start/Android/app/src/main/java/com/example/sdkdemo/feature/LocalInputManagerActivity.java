package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.LocalInputManager;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与本地输入{@link LocalInputManager}相关的功能接口
 * 使用该服务可以使用本地输入法完成对云端实例中输入框的文字输入。
 */
public class LocalInputManagerActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private LocalInputManager mLocalInputManager;
    private SwitchCompat mSwShowOrHide, mSwShowLocalData, mSwCloseLocalManager;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnCoverCurrentEditTextMessage, mBtnSendInputText, mBtnGetTextInputEnable;
    EditText mEtTextInput;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_local_input);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mEtTextInput = findViewById(R.id.et_text_input);
        mBtnCoverCurrentEditTextMessage = findViewById(R.id.btn_cover_current_edit_text_message);
        mBtnSendInputText = findViewById(R.id.btn_send_input_text);
        mBtnGetTextInputEnable = findViewById(R.id.btn_get_keyboard_status);
        mSwShowLocalData = findViewById(R.id.sw_show_local_data);
        mSwCloseLocalManager = findViewById(R.id.sw_close_input_manager);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * coverCurrentEditTextMessage(String text) -- 覆盖当前输入框的内容
         */
        mBtnCoverCurrentEditTextMessage.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.coverCurrentEditTextMessage(mEtTextInput.getText().toString());
            }
            else {
                Log.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * sendInputText(String text) -- 向当前输入框追加内容
         */
        mBtnSendInputText.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.sendInputText(mEtTextInput.getText().toString());
            }
            else {
                Log.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * enableShowCurrentInputText(boolean enable) -- 显示当前输入框内容
         */
        mSwShowLocalData.setChecked(false);
        mSwShowLocalData.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.enableShowCurrentInputText(isChecked);
            }
            else {
                Log.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * closeAutoKeyBoard(boolean isIntercept) -- 是否拦截SDK调起本地键盘
         *
         * @param isIntercept false -- 不拦截
         *                    true -- 拦截，由用户自行处理本地键盘的调起和内容的发送
         */
        mSwCloseLocalManager.setChecked(false);
        mSwCloseLocalManager.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.closeAutoKeyBoard(isChecked);
            }
            else {
                Log.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * 云端实例输入框是否支持发送文本
         * isTextInputEnable()
         *
         * @return 云端输入框可发送状态
         *         <li>true：可发送，此状态下允许调用{@link LocalInputManager#sendInputText(String)}接口向pod输入框发送文字</li>
         *         <li>false：不可发送</li>
         */
        mBtnGetTextInputEnable.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                showToast("" + mLocalInputManager.isTextInputEnable());
            }
            else {
                Log.e(TAG, "mLocalInputManager == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(SdkUtil.getClientUid())
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
        mLocalInputManager = VePhoneEngine.getInstance().getLocalInputManager();
        if (mLocalInputManager != null) {
            mLocalInputManager.setRemoteInputCallBack(new LocalInputManager.RemoteInputCallBack() {
                /**
                 * 云端输入法准备阶段的一些状态回调
                 *
                 * @param hintText 提示文本
                 * @param inputType 输入格式
                 */
                @Override
                public void onPrepare(String hintText, int inputType) {
                    Log.i(TAG, "[onPrepare] hintText: " + hintText + ", inputType: " + inputType);
                }

                /**
                 * 云端输入法软键盘请求弹出的回调，该回调会触发多次
                 */
                @Override
                public void onCommandShow() {
                    Log.i(TAG, "[onCommandShow]");
                }

                /**
                 * 云端输入法软键盘请求收起的回调
                 */
                @Override
                public void onCommandHide() {
                    Log.i(TAG, "[onCommandHide]");
                }

                /**
                 * 云端输入框内容变化的回调
                 *
                 * @param text 输入框内容发生变化后的文本信息
                 */
                @Override
                public void onTextChange(String text) {
                    Log.i(TAG, "[onTextChange] text: " + text);
                }

                /**
                 * 不适用于云手机场景，可忽略
                 */
                @Override
                public void onRemoteKeyBoardEnabled(boolean enable) {

                }

                /**
                 * 云端实例输入框是否支持发送文本状态变化回调
                 *
                 * @param enable true -- 支持
                 *               false -- 不支持
                 */
                @Override
                public void onTextInputEnableStateChanged(boolean enable) {
                    Log.i(TAG, "[onTextInputEnableStateChanged] enable: " + enable);
                }
            });
        }
        else {
            Log.e(TAG, "mLocalInputManager == null");
        }
    }

}

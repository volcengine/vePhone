package com.example.sdkdemo.feature;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.LocalInputManager;

public class LocalInputManagerView {

    private LocalInputManager localInputManager;
    private DialogUtils.DialogWrapper mDialogWrapper;

    public LocalInputManagerView(Context context, LocalInputManager localInputManager, Button btnLocalInput) {
        this.localInputManager = localInputManager;
        mDialogWrapper  = DialogUtils.wrapper(new TestView(context));
        btnLocalInput.setVisibility(View.VISIBLE);
        btnLocalInput.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends LinearLayout {

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_local_input, this);
            setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

            /**
             * coverCurrentEditTextMessage(String text) -- 设置当前输入框的内容
             */
            EditText inputView = findViewById(R.id.et_text_input);
            findViewById(R.id.btn_send_input_data).setOnClickListener(v -> {
                localInputManager.coverCurrentEditTextMessage(inputView.getText().toString());
            });

            /**
             * enableShowCurrentInputText(boolean enable) -- 显示当前输入框内容
             */
            SwitchCompat enableInput = findViewById(R.id.switch_show_local_data);
            enableInput.setChecked(false);
            enableInput.setOnCheckedChangeListener((buttonView, isChecked) ->
                    localInputManager.enableShowCurrentInputText(isChecked)
            );

            /**
             * closeAutoKeyBoard(boolean isIntercept) -- 是否拦截SDK调起本地键盘
             *
             * @param isIntercept false -- 不拦截
             *                    true -- 拦截，由用户自行处理本地键盘的调起和内容的发送
             */
            SwitchCompat enableAutoKeyBoard = findViewById(R.id.switch_close_input_manager);
            enableAutoKeyBoard.setChecked(false);
            enableAutoKeyBoard.setOnCheckedChangeListener((buttonView, isChecked) ->
                    localInputManager.closeAutoKeyBoard(isChecked)
            );

            /**
             * getKeyboardEnable() -- 获取远端实例输入法开关状态
             * setKeyBoardEnable(boolean enable) -- 设置远端实例输入法开关状态
             */
            SwitchCompat enableKeyBoard = findViewById(R.id.switch_close_input_keyboard);
            enableKeyBoard.setChecked(localInputManager.getKeyboardEnable());
            enableKeyBoard.setOnCheckedChangeListener((buttonView, isChecked) -> {
                if (!isChecked) {
                    InputMethodManager inputMethodManager = (InputMethodManager) context.getSystemService(Context.INPUT_METHOD_SERVICE);
                    inputMethodManager.hideSoftInputFromWindow(this.getWindowToken(), 0);
                }
                localInputManager.setKeyBoardEnable(isChecked);
            });
            findViewById(R.id.btn_get_keyboardEnable).setOnClickListener(v -> {
                Toast.makeText(context, "" + localInputManager.getKeyboardEnable(), Toast.LENGTH_SHORT).show();
            });
        }
    }
}

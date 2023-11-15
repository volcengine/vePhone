package com.example.sdkdemo.common;

import android.os.Environment;
import android.text.TextUtils;

import com.blankj.utilcode.util.ToastUtils;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;

public class AudioDumper {

    private volatile BufferedOutputStream os;
    private String mFilePath;

    public void close() {
        if (os != null) {
            try {
                os.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
            os = null;
            if (!TextUtils.isEmpty(mFilePath)) {
                ToastUtils.showLong("已保存至：" + mFilePath);
                mFilePath = null;
            }
        }
    }

    public void accept(byte[] frame) {
        final BufferedOutputStream fc = prepare();
        if (fc != null) {
            try {
                fc.write(frame);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private BufferedOutputStream prepare() {
        if (os == null) {
            try {
                File file = new File(
                        Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC),
                        "dump_local_" + System.currentTimeMillis() + ".pcm");
                mFilePath = file.getPath();
                os = new BufferedOutputStream(new FileOutputStream(file, true));
            } catch (FileNotFoundException e) {
                e.printStackTrace();
            }
        }
        return os;
    }
}

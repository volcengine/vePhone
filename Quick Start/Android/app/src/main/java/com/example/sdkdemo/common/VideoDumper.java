package com.example.sdkdemo.common;

import android.os.Environment;
import android.text.TextUtils;

import com.blankj.utilcode.util.ToastUtils;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;

public class VideoDumper {
    private volatile FileChannel mFileChannel;
    private volatile String mFilePath;
    private volatile ByteBuffer mBuffer;
    private final String mType;

    public VideoDumper(String type) {
        // nv21, i420
        mType = type;
    }

    public void close() {
        if (mFileChannel != null) {
            try {
                mFileChannel.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
            mFileChannel = null;
            if (!TextUtils.isEmpty(mFilePath)) {
                ToastUtils.showLong("已保存至：" + mFilePath);
                mFilePath = null;
            }
        }
    }


    public void accept(byte[] data) {
        final FileChannel fc = prepare();
        if (fc != null) {
            try {
                ByteBuffer buffer = mBuffer;
                if (buffer == null||buffer.capacity()<data.length) {
                    buffer = ByteBuffer.allocate(data.length);
                    mBuffer = buffer;
                }
                buffer.clear();
                buffer.put(data);
                buffer.flip();
                fc.write(buffer);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private FileChannel prepare() {
        if (mFileChannel == null) {
            try {
                File file = new File(
                        Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC),
                        "dump_" + System.currentTimeMillis() + "." + mType.toLowerCase());
                mFilePath = file.getPath();
                mFileChannel = new FileOutputStream(file, true).getChannel();
            } catch (FileNotFoundException e) {
                e.printStackTrace();
            }
        }
        return mFileChannel;
    }
}

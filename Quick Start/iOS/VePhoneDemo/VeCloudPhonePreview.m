//
//  VeCloudPhonePreview.m
//  VePlayerDemo
//
//  Created by ByteDance on 2023/1/4.
//  Copyright © 2023 ByteDance Ltd. All rights reserved.
//

#import "VeCloudPhonePreview.h"
#import <Masonry/Masonry.h>
#import <SDWebImage/SDWebImage.h>

@interface VeCloudPhonePreview ()

@property (nonatomic, strong) UIImageView *preview;
@property (nonatomic, strong) UIButton *closeButton;

@end

@implementation VeCloudPhonePreview

- (instancetype)initWithFrame:(CGRect)frame
{
    if (self = [super initWithFrame: frame]) {
        self.layer.masksToBounds = YES;
        self.layer.borderColor = [UIColor blackColor].CGColor;
        self.layer.borderWidth = 1.;
        _preview = [[UIImageView alloc] init];
        _preview.contentMode = UIViewContentModeScaleAspectFill;
        [self addSubview:_preview];
        [_preview mas_makeConstraints:^(MASConstraintMaker *make) {
            make.edges.equalTo(self);
        }];
        _closeButton = [UIButton buttonWithType: UIButtonTypeCustom];
        [_closeButton setImage: [UIImage imageNamed: @"close"] forState: UIControlStateNormal];
        _closeButton.backgroundColor = [UIColor lightGrayColor];
        [_closeButton addTarget: self action: @selector(closeButtonClicked:) forControlEvents: UIControlEventTouchUpInside];
        [self addSubview: _closeButton];
        [_closeButton mas_makeConstraints:^(MASConstraintMaker *make) {
            make.top.mas_equalTo(10);
            make.right.mas_equalTo(-10);
            make.size.mas_equalTo(CGSizeMake(30, 30));
        }];
    }
    return self;
}

- (void)loadImageWithUrl:(NSString *)url
{
    if (url.length > 0) {
        [_preview sd_setImageWithURL:[NSURL URLWithString:url] placeholderImage:nil completed:^(UIImage * _Nullable image, NSError * _Nullable error, SDImageCacheType cacheType, NSURL * _Nullable imageURL) {
        }];
    }
}

- (void)closeButtonClicked:(UIButton *)sender
{
    [self removeFromSuperview];

    _preview.image = nil;
}

@end

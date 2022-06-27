# Tmux学习文档

参考http://www.ruanyifeng.com/blog/2019/10/tmux.html

## 一. Tmux介绍

Tmux 是一个终端复用器（terminal multiplexer）



## 二. 安装

```bash
# Ubuntu 或 Debian
$ sudo apt-get install tmux
```

## 三. 常用操作

1. 常用操作：

- 新建会话 `tmux `或者` tmux new -s my_session`
- 连接到会话 `tmux attach -t my_session`
- 分离会话`tmux detach`
- 查看所有会话`tmux ls`
- 杀死会话`tmux kill-session -t`
- 切换会话`tmux switch -t`

2. 常用快捷键：

- `Ctrl+d` :  退出tmux

- `Ctrl+b d`：分离当前会话。

- `Ctrl+b s`：列出所有会话。

- `Ctrl+b $`：重命名当前会话。

## 四. 窗格操作

1. `tmux split-window`命令用来划分窗格。

   ```bash
   # 划分左右两个窗格
   $ tmux split-window -h
   
   # 划分上下两个窗格
   $ tmux split-window
   ```

2. `tmux select-pane`命令用来移动光标位置。

   ```bash
   # 光标切换到上方窗格
   $ tmux select-pane -U
   
   # 光标切换到下方窗格
   $ tmux select-pane -D
   
   # 光标切换到左边窗格
   $ tmux select-pane -L
   
   # 光标切换到右边窗格
   $ tmux select-pane -R
   ```

3. 窗格快捷键
   - `Ctrl+b %`：划分左右两个窗格。
   - `Ctrl+b "`：划分上下两个窗格。
   - `Ctrl+b <arrow key>`：光标切换到其他窗格。`<arrow key>`是指向要切换到的窗格的方向键，比如切换到下方窗格，就按方向键`↓`。
   - `Ctrl+b ;`：光标切换到上一个窗格。
   - `Ctrl+b o`：光标切换到下一个窗格。
   - `<C-b> <方向>` 切换到指定方向的面板，<方向> 指的是键盘上的方向键
   - `Ctrl+b z`：当前窗格全屏显示，再使用一次会变回原来大小。
   - `<C-b> [` 开始往回卷动屏幕。您可以按下空格键来开始选择，回车键复制选中的部分
   - `<C-b> <空格>` 在不同的面板排布间切换
   - 
   - `Ctrl+b {`：当前窗格与上一个窗格交换位置。
   - `Ctrl+b }`：当前窗格与下一个窗格交换位置。
   - `Ctrl+b Ctrl+o`：所有窗格向前移动一个位置，第一个窗格变成最后一个窗格。
   - `Ctrl+b Alt+o`：所有窗格向后移动一个位置，最后一个窗格变成第一个窗格。
   - `Ctrl+b x`：关闭当前窗格。
   - `Ctrl+b !`：将当前窗格拆分为一个独立窗口。
   - `Ctrl+b q`：显示窗格编号。

## 五. 窗口管理

 1. 新建窗口

    ```bash
    $ tmux new-window
    
    # 新建一个指定名称的窗口
    $ tmux new-window -n <window-name>
    ```

2. 切换窗口

   ```bash
   # 切换到指定编号的窗口
   $ tmux select-window -t <window-number>
   
   # 切换到指定名称的窗口
   $ tmux select-window -t <window-name>
   ```

3. 窗口快捷键
   - `Ctrl+b c`：创建一个新窗口，状态栏会显示多个窗口的信息。
   - `Ctrl+b p`：切换到上一个窗口（按照状态栏上的顺序）。
   - `Ctrl+b n`：切换到下一个窗口。
   - `Ctrl+b <number>`：切换到指定编号的窗口，其中的`<number>`是状态栏上的窗口编号。
   - `Ctrl+b w`：从列表中选择窗口。
   - `Ctrl+b ,`：窗口重命名。
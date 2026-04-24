// Type_plus.cpp
// 说明：一个简单的 Windows 鼠标点击示例程序，演示如何在指定位置发送鼠标左键点击。
// 注意：在现代 Windows 编程中建议使用 SendInput，而不是 mouse_event（mouse_event 已被标记为过时）。
//       此处使用 mouse_event 仅为保持与原始仓库一致的最小改动示例。

#include <iostream>
#include <Windows.h>

// 执行一次左键点击（当前位置）
void click_once() {
    // MOUSEEVENTF_LEFTDOWN 然后 MOUSEEVENTF_LEFTUP 表示一次单击
    mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
}

// 在指定次数和间隔执行点击
void clicker(int times = 1, int interval_ms = 100) {
    for (int i = 0; i < times; ++i) {
        click_once();
        Sleep(interval_ms);
    }
}

int main() {
    // 示例：执行 5 次点击，每次间隔 100 毫秒
    std::cout << "将执行 5 次鼠标左键点击（示例）" << std::endl;
    clicker(5, 100);
    return 0;
}

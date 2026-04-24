// 生成训练用验证码.cpp
// 简单的命令行工具：生成验证码
// 默认行为：生成 4 位仅数字验证码。可选 -a 生成字母数字验证码，-n <长度> 指定长度
// 生成训练用验证码（带中文注释）
// 说明：这个工具用于批量生成简短的验证码样本，用于训练 OCR 或验证码识别模型。
// 行为摘要：默认生成 4 位数字验证码，可以通过命令行参数改变长度、数量、是否包含字母等。
// 使用示例：生成 100 个包含字母数字的验证码并输出到指定目录
//   ./生成训练用验证码 -n 5 -c 100 -a -o "C:\\path\\to\\outdir"

#include <iostream>
#include <random>
#include <string>
#include <chrono>
#include <vector>
#include <algorithm>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <sstream>

// 生成单个验证码字符串
// length: 验证码长度；digits_only: 是否只使用数字；rng: 随机数引擎引用
std::string generate_code(int length, bool digits_only, std::mt19937 &rng) {
    if (length <= 0) length = 4;
    const std::string digits = "0123456789";
    // 排除易混淆字符：0,O,1,I
    const std::string alnum = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"; 

    const std::string &pool = digits_only ? digits : alnum;
    std::uniform_int_distribution<int> dist(0, static_cast<int>(pool.size()) - 1);

    std::string out;
    out.reserve(length);
    for (int i = 0; i < length; ++i) {
        out.push_back(pool[dist(rng)]);
    }
    return out;
}

int main(int argc, char** argv) {
    int length = 4;
    bool digits_only = true; // 默认仅数字
    long long count = 1; // 默认生成 1 个
    // 默认输出目录（可通过 -o 指定）
    std::string outdir = "C:\\Users\\LENOVO\\Desktop\\指定网站连点器\\training data";
    bool single_csv = false; // 是否只生成单个 CSV 文件

    // 解析简单的命令行参数（无需依赖外部库）
    for (int i = 1; i < argc; ++i) {
        std::string s = argv[i];
        if (s == "-h" || s == "--help") {
            std::cout << "用法: " << argv[0] << " [-n 长度] [-a] [-c 数量] [-o 输出目录]\n";
            std::cout << " -n <长度>   指定验证码长度 (默认 4)\n";
            std::cout << " -a          使用字母+数字(排除易混淆字符) 而不是仅数字\n";
            std::cout << " -c <数量>   生成多个验证码 (默认 1)\n";
            std::cout << " -o <目录>   将每个样本写为单独文件，并生成 index.csv (默认目录如代码中)\n";
            std::cout << " -S          只生成单个 CSV 文件 dataset.csv (包含 filename,label,text)\n";
            return 0;
        } else if (s == "-a" || s == "--alnum") {
            digits_only = false;
        } else if (s == "-n" || s == "--length") {
            if (i + 1 < argc) {
                try {
                    int v = std::stoi(argv[++i]);
                    if (v > 0) length = v;
                } catch (...) {
                    // 解析失败则使用默认值
                }
            }
        } else if (s == "-c" || s == "--count") {
            if (i + 1 < argc) {
                try {
                    long long v = std::stoll(argv[++i]);
                    if (v > 0) count = v;
                } catch (...) {
                    // 解析失败则使用默认值
                }
            }
        } else if (s == "-o" || s == "--outdir") {
            if (i + 1 < argc) {
                outdir = argv[++i];
            }
        } else if (s == "-S" || s == "--single-csv") {
            single_csv = true;
        }
    }

    // 限制长度和数量范围以防滥用
    if (length < 1) length = 1;
    if (length > 64) length = 64;

    if (count < 1) count = 1;
    if (count > 10000000) count = 10000000; // safety cap

    // 初始化随机数引擎（单次 seed）
    std::random_device rd;
    auto now = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    std::seed_seq seed{rd(), static_cast<unsigned int>(now & 0xffffffffu), static_cast<unsigned int>((now>>32) & 0xffffffffu)};
    std::mt19937 rng(seed);

    if (outdir.empty()) {
        // 如果未指定输出目录，则输出到 stdout（每行为一个验证码）
        for (long long i = 0; i < count; ++i) {
            std::string code = generate_code(length, digits_only, rng);
            std::cout << code << '\n';
        }
        return 0;
    }

    // 创建输出目录
    std::filesystem::path od(outdir);
    try {
        std::filesystem::create_directories(od);
    } catch (...) {
        std::cerr << "无法创建输出目录: " << outdir << std::endl;
        return 2;
    }

    if (single_csv) {
        // 生成单个 dataset.csv，包含 filename,label,text 三列
        std::filesystem::path csv_path = od / "dataset.csv";
        std::ofstream csv_fs(csv_path);
        if (!csv_fs) {
            std::cerr << "无法创建 CSV 文件: " << csv_path << std::endl;
            return 3;
        }
        csv_fs << "filename,label,text\n";
        for (long long i = 1; i <= count; ++i) {
            std::string code = generate_code(length, digits_only, rng);
            std::ostringstream fname;
            fname << "sample_" << std::setw(6) << std::setfill('0') << i << "_" << code << ".txt";
            csv_fs << fname.str() << "," << code << "," << code << "\n";
        }
    } else {
        // 生成每个样本单独文件，并写入 index.csv
        std::filesystem::path index_path = od / "index.csv";
        std::ofstream index_fs(index_path);
        if (!index_fs) {
            std::cerr << "无法创建索引文件: " << index_path << std::endl;
            return 3;
        }
        index_fs << "filename,label\n";

        // 每个文件名格式: sample_000001_<code>.txt
        for (long long i = 1; i <= count; ++i) {
            std::string code = generate_code(length, digits_only, rng);
            std::ostringstream fname;
            fname << "sample_" << std::setw(6) << std::setfill('0') << i << "_" << code << ".txt";
            std::filesystem::path file_path = od / fname.str();
            std::ofstream fs(file_path);
            if (!fs) {
                std::cerr << "无法写入文件: " << file_path << std::endl;
                continue;
            }
            fs << code;
            index_fs << fname.str() << "," << code << "\n";
        }
    }

    std::cout << "生成完成: " << count << " 个样本，输出目录: " << outdir << std::endl;
    return 0;
}

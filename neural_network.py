"""
neural_network.py
说明：一个简化且被注释的 PyTorch CNN 示例，用于验证码识别研究。

注意说明：
 - 该文件只演示模型结构、训练/评估接口和预测接口。
 - 数据加载器（train_dl/test_dl）需由用户实现（例如使用 torchvision.datasets 或自定义 Dataset）。
 - 训练循环中的具体超参和保存策略可按需调整。
"""

import torch
import torch.nn as nn


class CNN(nn.Module):
    """一个简单的卷积网络，用于演示（并非经过调优的生产模型）。
    假设输出为 4 个字符，每个字符有 10 个类别 -> 最终输出大小为 40。
    """
    def __init__(self):
        super(CNN, self).__init__()
        self.hidden1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        nn.init.kaiming_uniform_(self.hidden1.weight, nonlinearity='leaky_relu')
        self.act1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(2, 2)

        self.hidden2 = nn.Conv2d(32, 32, kernel_size=3, padding=1)
        self.act2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(2, 2)

        self.hidden3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.act3 = nn.ReLU()
        self.pool3 = nn.MaxPool2d(2, 2)

        # 下面线性层的输入尺寸取决于输入图片大小，示例值为 64*4*10
        self.hidden4 = nn.Linear(64 * 4 * 10, 128)
        self.act4 = nn.ReLU()
        self.out = nn.Linear(128, 4 * 10)
        nn.init.xavier_uniform_(self.out.weight)
        self.sm = nn.Softmax(dim=1)

    def forward(self, X):
        X = self.hidden1(X)
        X = self.act1(X)
        X = self.pool1(X)
        X = self.hidden2(X)
        X = self.act2(X)
        X = self.pool2(X)
        X = self.hidden3(X)
        X = self.act3(X)
        X = self.pool3(X)
        X = X.view(-1, 64 * 4 * 10)
        X = self.hidden4(X)
        X = self.act4(X)
        X = self.out(X)
        X = self.sm(X)
        return X


def evaluate_model(model, test_dl):
    """评估模型在 test_dl（可迭代对象，返回 (inputs, labels)）上的准确率."""
    correct = 0
    total = 0
    model.eval()
    with torch.no_grad():
        for inputs, labels in test_dl:
            outputs = model(inputs)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    if total == 0:
        return 0.0
    accuracy = 100.0 * correct / total
    return accuracy


def train_model(train_dl, model, test_dl, epochs=10):
    """训练模型的简单实现。
    train_dl 和 test_dl 应该是 PyTorch DataLoader 实例。
    """
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    for epoch in range(epochs):
        model.train()
        for i, (inputs, labels) in enumerate(train_dl):
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
        accuracy = evaluate_model(model, test_dl)
        print(f'Epoch {epoch + 1}, Accuracy: {accuracy:.2f}%')
        if accuracy > 95:
            torch.save(model.state_dict(), 'cnn_model.pth')
            return
    torch.save(model.state_dict(), 'cnn_model.pth')


def predict(model, image):
    """对 image（Tensor 或 batch）进行预测并返回标签."""
    model.eval()
    with torch.no_grad():
        output = model(image)
        _, predicted = torch.max(output.data, 1)
    return predicted






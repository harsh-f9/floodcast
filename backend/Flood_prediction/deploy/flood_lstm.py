
import torch
import torch.nn as nn

class FloodLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, dropout):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=False
        )
        self.layer_norm = nn.LayerNorm(hidden_size)
        self.dropout    = nn.Dropout(dropout)
        self.fc1        = nn.Linear(hidden_size, hidden_size // 2)
        self.act        = nn.GELU()
        self.fc2        = nn.Linear(hidden_size // 2, 1)

    def forward(self, x, return_hidden=False):
        lstm_out, _  = self.lstm(x)
        last_out     = lstm_out[:, -1, :]
        last_normed  = self.layer_norm(last_out)
        out          = self.dropout(last_normed)
        out          = self.act(self.fc1(out))
        out          = self.dropout(out)
        pred         = self.fc2(out).squeeze(-1)
        if return_hidden:
            return pred, last_normed
        return pred

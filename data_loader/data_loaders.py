import soundfile as sf
import json
from base import BaseDataLoader
from torch.utils.data import Dataset
import os
import pandas as pd
import random
import numpy as np
from librosa import load
from tqdm import tqdm
from functools import partial
from concurrent.futures import ProcessPoolExecutor


class _MusicNetDataset(Dataset):
    """s
    MusicNet Dataset.
    """
    train_data = 'train_data'
    test_data = 'test_data'
    metafile = 'musicnet_metadata.csv'

    def __init__(self,
                 data_dir,
                 size,
                 n_workers,
                 sr=None,
                 segment=16384,
                 training=True,
                 category='all'):
        self.segment = segment
        self.sr = sr
        self.data_dir = os.path.expanduser(data_dir)
        self.size = size

        metadata = pd.read_csv(os.path.join(data_dir, self.metafile))
        if category == 'all':
            ids = metadata['id'].values.tolist()
        else:
            idx = metadata.index[metadata['ensemble'] == category]
            ids = metadata.loc[idx]['id'].values.tolist()

        if not training:
            self.data_path = os.path.join(self.data_dir, self.test_data)
        else:
            self.data_path = os.path.join(self.data_dir, self.train_data)

        self.waves = []
        load_fn = partial(load, sr=self.sr)
        with ProcessPoolExecutor(n_workers) as executor:
            futures = [executor.submit(load_fn, os.path.join(self.data_path, f)) for f in os.listdir(self.data_path) if
                       f.endswith('.wav') and int(f[:-4]) in ids]
            for future in tqdm(futures):
                y, _ = future.result()
                self.waves.append(y)

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        wav = random.choice(self.waves)
        pos = random.randint(0, len(wav) - self.segment - 1)
        x = wav[pos:pos + self.segment]
        return x


class _WAVDataset(Dataset):
    """
    Wave-file-only Dataset.
    """

    def __init__(self,
                 data_dir,
                 size,
                 segment):
        self.segment = segment
        self.data_path = os.path.expanduser(data_dir)
        self.size = size

        self.waves = []
        self.sr = None
        self.files = []
        self.file_lengths = []

        def get_nframes(info_str):
            try:
                return int(f_obj.extra_info.split('frames  : ')[1].split('\n')[0])
            except:
                byte_sec = int(info_str.split('Bytes/sec     : ')[1].split('\n')[0])
                data = int(info_str.split('data : ')[1].split('\n')[0])
                sr = int(info_str.split('Sample Rate   : ')[1].split('\n')[0])
                return int(data / byte_sec * sr)

        print("Gathering training files ...")
        metadata = json.load(open(os.path.join('/data/yinjyun/datasets/', 'maestro-v2.0.0.json')))
        files = sorted([os.path.join(self.data_path, row['audio_filename']) 
                    for row in metadata if row['split'] == 'train'])
        # print(files)
        # for f in tqdm(os.listdir(self.data_path)):
        for f in tqdm(files):
            if f.endswith('.wav'):
                # filename = os.path.join(self.data_path, f)
                # f_obj = sf.SoundFile(filename)
                f_obj = sf.SoundFile(f)
                self.files.append(f_obj)
                self.file_lengths.append(get_nframes(f_obj.extra_info))

                if not self.sr:
                    self.sr = f_obj.samplerate
                else:
                    assert f_obj.samplerate == self.sr
        self.file_lengths = np.array(self.file_lengths)
        self.boundaries = np.cumsum(self.file_lengths) / (self.file_lengths.sum() - 1)

        # normalization value based on each file
        # will updated on the fily
        self.max_values = np.zeros_like(self.boundaries)

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        index = np.digitize(random.uniform(0, 1), self.boundaries)
        f, length = self.files[index], self.file_lengths[index]
        pos = random.randint(0, length - 1)
        f.seek(pos)
        x = f.read(self.segment, dtype='float32', always_2d=True, fill_value=0.).mean(1)
        max_abs = np.abs(x).max()
        if max_abs > self.max_values[index]:
            self.max_values[index] = max_abs
        x /= self.max_values[index]
        return x


class MusicNetDataLoader(BaseDataLoader):
    """
    MNIST data loading demo using BaseDataLoader
    """

    def __init__(self, steps, data_dir, batch_size, num_workers, **kwargs):
        self.data_dir = data_dir
        self.dataset = _MusicNetDataset(data_dir, batch_size * steps, num_workers, **kwargs)
        super().__init__(self.dataset, batch_size, False, 0, num_workers)


class RandomWaveFileLoader(BaseDataLoader):
    """
    MNIST data loading demo using BaseDataLoader
    """

    def __init__(self, steps, data_dir, batch_size, num_workers, **kwargs):
        self.data_dir = data_dir
        self.dataset = _WAVDataset(data_dir, batch_size * steps, **kwargs)
        super().__init__(self.dataset, batch_size, False, 0., num_workers)


if __name__ == '__main__':
    loader = RandomWaveFileLoader(100, '/media/ycy/86A4D88BA4D87F5D/DataSet/LJSpeech-1.1/wavs', 1, 0, segment=16000)

    import matplotlib.pyplot as plt
    for x in loader:
        plt.plot(x[0].numpy())
        plt.show()

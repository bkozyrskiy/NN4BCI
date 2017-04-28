from Data import *
from keras.layers import Convolution1D, Dense, Dropout, Input, merge, GlobalMaxPooling1D
from keras.models import Model
from keras.optimizers import RMSprop
from keras.callbacks import EarlyStopping,TensorBoard,ReduceLROnPlateau
from keras import backend as K
from scipy.signal import resample
from uuid import uuid4


def get_base_model(input_len, fsize,channel_number):
    '''Base network to be shared (eq. to feature extraction).
    '''
    input_seq = Input(shape=(input_len, channel_number))
    nb_filters = 50
    convolved = Convolution1D(nb_filters, fsize, border_mode="same", activation="relu")(input_seq)
    convolved = Dropout(0.7)(convolved)
    pooled = GlobalMaxPooling1D()(convolved)
    compressed = Dense(50, activation="relu")(pooled)
    compressed = Dropout(0.7)(compressed)
    compressed = Dense(50, activation="relu")(compressed)
    compressed = Dropout(0.7)(compressed)
    model = Model(input=input_seq, output=compressed)
    return model

def get_full_model(channel_number,epoch_len):
    # input_quarter_seq = Input(shape=(int(epoch_len/4), channel_number))
    # input_half_seq = Input(shape=(int(epoch_len/2), channel_number))
    input_full_seq = Input(shape=(epoch_len, channel_number))

    # base_network_quarter = get_base_model(int(epoch_len/4), 10,channel_number)
    # base_network_half = get_base_model(int(epoch_len/2), 10,channel_number)
    base_network_full = get_base_model(epoch_len, 10,channel_number)

    # embedding_quarter = base_network_quarter(input_quarter_seq)
    # embedding_half = base_network_half(input_half_seq)
    embedding_full = base_network_full(input_full_seq)

    # merged = merge([embedding_quarter, embedding_half, embedding_full], mode="concat")
    out = Dense(2, activation='softmax')(embedding_full)

    model = Model(input=[input_full_seq], output=out)

    opt = RMSprop(lr=0.00005, clipvalue=10**6)
    model.compile(loss='categorical_crossentropy',metrics=['accuracy'], optimizer=opt)
    return model


def to_onehot(y):
    onehot = np.zeros((len(y),2))
    onehot[range(len(y)),y] = 1
    return onehot

def get_resampled_data(data,axis):
    # @axis - axis of time to resempling
    epoch_len = data.shape[axis]
    return [resample(data,epoch_len/4,axis=axis),resample(data,epoch_len/2,axis=axis),data]

if __name__=='__main__':
    experiment='em01'
    data_source = NeuromagData('mag')
    dim_order = ['trial','time','channel']
    X,y=data_source.get_all_data(experiment,dim_order)
    dev = Neuromag('mag')
    augmenter = DataAugmentation(device=dev)
    Xm = augmenter.mirror_sensors(X)
    X = np.concatenate((X,Xm),axis=0)
    y = np.hstack((y,y))
    X = (X - np.mean(X, axis=0)) / np.std(X, axis=0)
    model = get_full_model(X.shape[2],X.shape[1])
    nb_epoch = 10000
    early_stopping = EarlyStopping(monitor='val_loss', patience=100, verbose=0, mode='auto')
    tensor_board = TensorBoard(log_dir = './logs/'+str(uuid4()), histogram_freq = 3)
    reduce_lr = ReduceLROnPlateau(min_lr=0,patience=50)
    with K.tf.device('/gpu:2'):
        model.fit(x=get_resampled_data(X,axis=1),y=to_onehot(y),batch_size=30, nb_epoch = nb_epoch,
                            callbacks=[tensor_board,reduce_lr], verbose=1, validation_split=0.2,shuffle=True)
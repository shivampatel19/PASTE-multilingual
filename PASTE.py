import sys
import os
import numpy as np
import random

from collections import OrderedDict
import pickle
import datetime
import json
from tqdm import tqdm
from recordclass import recordclass
import math
import torch
import torch.autograd as autograd
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
torch.backends.cudnn.deterministic = True

import regex as re
import spacy
from spacy.tokenizer import Tokenizer
nlp = spacy.load("en_core_web_sm")
nlp.tokenizer = Tokenizer(nlp.vocab, token_match=re.compile(r'\S+').match)


def custom_print(*msg):
	for i in range(0, len(msg)):
		if i == len(msg) - 1:
			print(msg[i])
			logger.write(str(msg[i]) + '\n')
		else:
			print(msg[i], ' ', end='')
			logger.write(str(msg[i]))


def load_word_embedding(embed_file, vocab):
	custom_print('vocab length:', len(vocab))
	custom_print(embed_file)
	embed_vocab = OrderedDict()
	embed_matrix = list()

	embed_vocab['<PAD>'] = 0
	embed_matrix.append(np.zeros(word_embed_dim, dtype=np.float32))

	embed_vocab['<UNK>'] = 1
	embed_matrix.append(np.random.uniform(-0.25, 0.25, word_embed_dim))

	word_idx = 2
	with open(embed_file, "r") as f:
		for line in f:
			parts = line.split()
			if len(parts) < word_embed_dim + 1:
				continue
			word = parts[0]
			if word in vocab:
				vec = [np.float32(val) for val in parts[1:]]
				embed_matrix.append(vec)
				embed_vocab[word] = word_idx
				word_idx += 1

	for word in vocab:
		if word not in embed_vocab and vocab[word] >= word_min_freq:
			embed_matrix.append(np.random.uniform(-0.25, 0.25, word_embed_dim))
			embed_vocab[word] = word_idx
			word_idx += 1

	custom_print('embed dictionary length:', len(embed_vocab))
	return embed_vocab, np.array(embed_matrix, dtype=np.float32)


def build_vocab(tr_data, dv_data, ts_data, save_vocab, embedding_file):
	vocab = OrderedDict()
	char_v = OrderedDict()
	char_v['<PAD>'] = 0
	char_v['<UNK>'] = 1
	char_idx = 2
	for d in tr_data:
		for word in d.SrcWords:
			if lower_cased:
				word = word.lower()
			if word not in vocab:
				vocab[word] = 1
			else:
				vocab[word] += 1

			for c in word:
				if c not in char_v:
					char_v[c] = char_idx
					char_idx += 1

	for d in dv_data + ts_data:
		for word in d.SrcWords:
			if lower_cased:
				word = word.lower()

			if word not in vocab:
				vocab[word] = 0

			for c in word:
				if c not in char_v:
					char_v[c] = char_idx
					char_idx += 1

	word_v, embed_matrix = load_word_embedding(embedding_file, vocab)
	output = open(save_vocab, 'wb')
	pickle.dump([word_v, char_v, pos_vocab, dep_vocab], output)
	output.close()
	return word_v, char_v, embed_matrix


def build_pos_tags(file1, file2, file3):
	f1 = open(file1, "r")
	f2 = open(file2, "r")
	f3 = open(file3, "r")
	pos_vocab = OrderedDict()
	pos_vocab['<PAD>'] = 0
	pos_vocab['<UNK>'] = 1
	k = 2
	for line in f1:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.pos_ if tok.pos_ == 'PUNCT' else tok.pos_ + "-" + tok.tag_ for tok in doc]
		for t in tags:
			if t not in pos_vocab:
				pos_vocab[t] = k
				k += 1
	for line in f2:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.pos_ if tok.pos_ == 'PUNCT' else tok.pos_ + "-" + tok.tag_ for tok in doc]
		for t in tags:
			if t not in pos_vocab:
				pos_vocab[t] = k
				k += 1
	for line in f3:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.pos_ if tok.pos_ == 'PUNCT' else tok.pos_ + "-" + tok.tag_ for tok in doc]
		for t in tags:
			if t not in pos_vocab:
				pos_vocab[t] = k
				k += 1
	return pos_vocab


def build_dep_tags(file1, file2, file3):
	f1 = open(file1, "r")
	f2 = open(file2, "r")
	f3 = open(file3, "r")
	dep_vocab = OrderedDict()
	dep_vocab['<PAD>'] = 0
	dep_vocab['<UNK>'] = 1
	k = 2
	for line in f1:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.dep_ for tok in doc]
		for t in tags:
			if t not in dep_vocab:
				dep_vocab[t] = k
				k += 1
	for line in f2:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.dep_ for tok in doc]
		for t in tags:
			if t not in dep_vocab:
				dep_vocab[t] = k
				k += 1
	for line in f3:
		line = line.strip()
		doc = nlp(line)
		tags = [tok.dep_ for tok in doc]
		for t in tags:
			if t not in dep_vocab:
				dep_vocab[t] = k
				k += 1
	return dep_vocab


def load_vocab(vocab_file):
	with open(vocab_file, 'rb') as f:
		embed_vocab, char_vocab, pos_vocab, dep_vocab = pickle.load(f)
	return embed_vocab, char_vocab, pos_vocab, dep_vocab


def get_sample(uid, src_line, trg_line, datatype):
	src_words = src_line.split(' ')
	trg_rels = []
	trg_pointers = []
	parts = trg_line.split('|')
	triples = []
	for part in parts:
		elements = part.strip().split(' ')
		triples.append((int(elements[0]), int(elements[1]), int(elements[2]), int(elements[3]),
						relnameToIdx[elements[4]]))

	if datatype == 1:
		if trip_order == triplet_orders[0]:
			random.shuffle(triples)
		elif trip_order == triplet_orders[1]:
			triples = sorted(triples, key=lambda element: (element[0], element[2]))
		else:
			triples = sorted(triples, key=lambda element: (element[2], element[0]))
	for triple in triples:
		trg_rels.append(triple[4])
		trg_pointers.append((triple[0], triple[1], triple[2], triple[3]))

	if datatype == 1 and (len(src_words) > max_src_len or len(trg_rels) > max_trg_len):
		return False, None

	sample = Sample(Id=uid, SrcLen=len(src_words), SrcWords=src_words, TrgLen=len(trg_rels), TrgRels=trg_rels,
					TrgPointers=trg_pointers)
	return True, sample


def get_data(src_lines, trg_lines, datatype):
	samples = []
	uid = 1
	for i in range(0, len(src_lines)):
		src_line = src_lines[i].strip()
		trg_line = trg_lines[i].strip()
		status, sample = get_sample(uid, src_line, trg_line, datatype)
		if status:
			samples.append(sample)
			uid += 1

		if use_data_aug and datatype == 1:
			parts = trg_line.split('|')
			if len(parts) == 1:
				continue
			for j in range(1, 2):
				status, aug_sample = get_sample(uid, src_line, trg_line, datatype)
				if status:
					samples.append(aug_sample)
					uid += 1
	return samples


def read_data(src_file, trg_file, datatype):
	reader = open(src_file)
	src_lines = reader.readlines()
	custom_print('No. of sentences:', len(src_lines))
	reader.close()

	reader = open(trg_file)
	trg_lines = reader.readlines()
	reader.close()

	data = get_data(src_lines, trg_lines, datatype)
	return data


def get_relations(file_name):
	nameToIdx = OrderedDict()
	idxToName = OrderedDict()
	reader = open(file_name)
	lines = reader.readlines()
	reader.close()
	nameToIdx['<PAD>'] = 0
	idxToName[0] = '<PAD>'
	# nameToIdx['<SOS>'] = 1
	# idxToName[1] = '<SOS>'
	nameToIdx['None'] = 1
	idxToName[1] = 'None'
	idx = 2
	if use_nr_triplets:
		nameToIdx['NR'] = 2
		idxToName[2] = 'NR'
		idx = 3
	for line in lines:
		nameToIdx[line.strip()] = idx
		idxToName[idx] = line.strip()
		idx += 1
	return nameToIdx, idxToName


def get_answer_pointers(arg1start_preds, arg1end_preds, arg2start_preds, arg2end_preds, sent_len):
	arg1_prob = -1.0
	arg1start = -1
	arg1end = -1
	max_ent_len = 5
	window = 100
	for i in range(0, sent_len):
		for j in range(i, min(sent_len, i + max_ent_len)):
			if arg1start_preds[i] * arg1end_preds[j] > arg1_prob:
				arg1_prob = arg1start_preds[i] * arg1end_preds[j]
				arg1start = i
				arg1end = j

	arg2_prob = -1.0
	arg2start = -1
	arg2end = -1
	for i in range(max(0, arg1start - window), arg1start):
		for j in range(i, min(arg1start, i + max_ent_len)):
			if arg2start_preds[i] * arg2end_preds[j] > arg2_prob:
				arg2_prob = arg2start_preds[i] * arg2end_preds[j]
				arg2start = i
				arg2end = j
	for i in range(arg1end + 1, min(sent_len, arg1end + window)):
		for j in range(i, min(sent_len, i + max_ent_len)):
			if arg2start_preds[i] * arg2end_preds[j] > arg2_prob:
				arg2_prob = arg2start_preds[i] * arg2end_preds[j]
				arg2start = i
				arg2end = j
	# return arg1start, arg1end, arg2start, arg2end

	arg2_prob1 = -1.0
	arg2start1 = -1
	arg2end1 = -1
	for i in range(0, sent_len):
		for j in range(i, min(sent_len, i + max_ent_len)):
			if arg2start_preds[i] * arg2end_preds[j] > arg2_prob1:
				arg2_prob1 = arg2start_preds[i] * arg2end_preds[j]
				arg2start1 = i
				arg2end1 = j

	arg1_prob1 = -1.0
	arg1start1 = -1
	arg1end1 = -1
	for i in range(max(0, arg2start1 - window), arg2start1):
		for j in range(i, min(arg2start1, i + max_ent_len)):
			if arg1start_preds[i] * arg1end_preds[j] > arg1_prob1:
				arg1_prob1 = arg1start_preds[i] * arg1end_preds[j]
				arg1start1 = i
				arg1end1 = j
	for i in range(arg2end1 + 1, min(sent_len, arg2end1 + window)):
		for j in range(i, min(sent_len, i + max_ent_len)):
			if arg1start_preds[i] * arg1end_preds[j] > arg1_prob1:
				arg1_prob1 = arg1start_preds[i] * arg1end_preds[j]
				arg1start1 = i
				arg1end1 = j
	if arg1_prob * arg2_prob > arg1_prob1 * arg2_prob1:
		return arg1start, arg1end, arg2start, arg2end
	else:
		return arg1start1, arg1end1, arg2start1, arg2end1


def is_full_match(triplet, triplets):
	for t in triplets:
		if t[0] == triplet[0] and t[1] == triplet[1] and t[2] == triplet[2]:
			return True
	return False


def get_gt_triples(src_words, rels, pointers):
	triples = []
	i = 0
	for r in rels:
		arg1 = ' '.join(src_words[pointers[i][0]:pointers[i][1] + 1])
		arg2 = ' '.join(src_words[pointers[i][2]:pointers[i][3] + 1])
		triplet = (arg1.strip(), arg2.strip(), relIdxToName[r])
		if not is_full_match(triplet, triples):
			triples.append(triplet)
		i += 1
	return triples


def get_pred_triples(rel, arg1s, arg1e, arg2s, arg2e, src_words):
	triples = []
	all_triples = []
	for i in range(0, len(rel)):
		pred_idx = np.argmax(rel[i][1:]) + 1
		pred_score = np.max(rel[i][1:])
		if pred_idx == relnameToIdx['None']:
			break
		if use_nr_triplets and pred_idx == relnameToIdx['NR']:
			continue
		
		s1, e1, s2, e2 = get_answer_pointers(arg1s[i], arg1e[i], arg2s[i], arg2e[i], len(src_words))
		arg1 = ' '.join(src_words[s1: e1 + 1])
		arg2 = ' '.join(src_words[s2: e2 + 1])
		arg1 = arg1.strip()
		arg2 = arg2.strip()
		if arg1 == arg2:
			continue
		triplet = (arg1, arg2, relIdxToName[pred_idx], pred_score)
		all_triples.append(triplet)
		if not is_full_match(triplet, triples):
			triples.append(triplet)
	return triples, all_triples


def get_F1(data, preds):
	gt_pos = 0
	pred_pos = 0
	total_pred_pos = 0
	correct_pos = 0
	for i in range(0, len(data)):
		gt_triples = get_gt_triples(data[i].SrcWords, data[i].TrgRels, data[i].TrgPointers)

		pred_triples, all_pred_triples = get_pred_triples(preds[0][i], preds[1][i], preds[2][i], preds[3][i],
														  preds[4][i], data[i].SrcWords)
		total_pred_pos += len(all_pred_triples)
		gt_pos += len(gt_triples)
		pred_pos += len(pred_triples)
		for gt_triple in gt_triples:
			if is_full_match(gt_triple, pred_triples):
				correct_pos += 1
	print(total_pred_pos)
	return pred_pos, gt_pos, correct_pos


def print_scores(gt_pos, pred_pos, correct_pos):
	custom_print('GT Triple Count:', gt_pos, '\tPRED Triple Count:', pred_pos, '\tCORRECT Triple Count:', correct_pos)
	test_p = float(correct_pos) / (pred_pos + 1e-8)
	test_r = float(correct_pos) / (gt_pos + 1e-8)
	test_acc = (2 * test_p * test_r) / (test_p + test_r + 1e-8)
	custom_print('Test P:', round(test_p, 3))
	custom_print('Test R:', round(test_r, 3))
	custom_print('Test F1:', round(test_acc, 3))


def get_splitted_F1(data, preds):
	total_count = 0
	gt_pos = 0
	pred_pos = 0
	correct_pos = 0
	
	count_single = 0
	gt_single = 0
	pred_single = 0
	correct_single = 0
	
	count_multi = 0
	gt_multi = 0
	pred_multi = 0
	correct_multi = 0
	
	count_multiRel = 0
	gt_multiRel = 0
	pred_multiRel = 0
	correct_multiRel = 0
	
	count_overlappingEnt = 0
	gt_overlappingEnt = 0
	pred_overlappingEnt = 0
	correct_overlappingEnt = 0
	
	for i in range(0, len(data)):
		total_count += 1
		gt_triples = get_gt_triples(data[i].SrcWords, data[i].TrgRels, data[i].TrgPointers)

		pred_triples, _ = get_pred_triples(preds[0][i], preds[1][i], preds[2][i], preds[3][i],
														  preds[4][i], data[i].SrcWords)		
		correct_count = 0
		gt_pos += len(gt_triples)
		pred_pos += len(pred_triples)
		for gt_triple in gt_triples:
			if is_full_match(gt_triple, pred_triples):
				correct_count += 1
				correct_pos += 1

		if len(data[i].TrgRels) == 1:
			count_single += 1
			gt_single += len(gt_triples)
			pred_single += len(pred_triples)
			correct_single += correct_count		
		else:
			count_multi += 1
			gt_multi += len(gt_triples)
			pred_multi += len(pred_triples)
			correct_multi += correct_count

			unique_rels = set(data[i].TrgRels)
			if len(unique_rels) > 1:
				count_multiRel += 1
				gt_multiRel += len(gt_triples)
				pred_multiRel += len(pred_triples)
				correct_multiRel += correct_count
			
			flag = 0
			for j in range(len(data[i].TrgPointers)):
				for k in range(len(data[i].TrgPointers)):
					if j == k:
						continue
					if data[i].TrgPointers[j][0] == data[i].TrgPointers[k][0] and data[i].TrgPointers[j][1] == data[i].TrgPointers[k][1]:
						flag = 1
						break
					if data[i].TrgPointers[j][2] == data[i].TrgPointers[k][2] and data[i].TrgPointers[j][3] == data[i].TrgPointers[k][3]:
						flag = 1
						break
					if data[i].TrgPointers[j][0] == data[i].TrgPointers[k][2] and data[i].TrgPointers[j][1] == data[i].TrgPointers[k][3]:
						flag = 1
						break
					if data[i].TrgPointers[j][2] == data[i].TrgPointers[k][0] and data[i].TrgPointers[j][3] == data[i].TrgPointers[k][1]:
						flag = 1
						break
				if flag == 1:
					break
			if flag == 1:
				count_overlappingEnt += 1
				gt_overlappingEnt += len(gt_triples)
				pred_overlappingEnt += len(pred_triples)
				correct_overlappingEnt += correct_count
		
	custom_print('Re-checking the scores of entire Test data with the best saved model:')
	custom_print('Total sentences in the test set:', total_count)
	print_scores(gt_pos, pred_pos, correct_pos)
	custom_print('Now printing the scores for various subsets of Test Data with the best saved model:')
	custom_print('Total sentences with single triples:', count_single)
	print_scores(gt_single, pred_single, correct_single)
	custom_print('Total sentences with multiple triples:', count_multi)
	print_scores(gt_multi, pred_multi, correct_multi)
	custom_print('Total sentences triples with varying sentiments:', count_multiRel)
	print_scores(gt_multiRel, pred_multiRel, correct_multiRel)
	custom_print('Total sentences with overlapping triples:', count_overlappingEnt)
	print_scores(gt_overlappingEnt, pred_overlappingEnt, correct_overlappingEnt)


def write_test_res(src, trg, data, preds, outfile):
	reader = open(src)
	src_lines = reader.readlines()
	writer = open(outfile, 'w')
	for i in range(0, len(data)):
		writer.write(src_lines[i])
		writer.write('Expected: '+trg[i])
		pred_triples, _ = get_pred_triples(preds[0][i], preds[1][i], preds[2][i], preds[3][i], preds[4][i],
										data[i].SrcWords)
		pred_triples_str = []
		for pt in pred_triples:
			str_tmp = pt[0] + ' ; ' + pt[1] + ' ; ' + pt[2] + ' ; ' + str(pt[3])
			if str_tmp not in pred_triples_str:
				pred_triples_str.append(str_tmp)
		writer.write('Predicted: ' + ' | '.join(pred_triples_str) + '\n'+'\n')
	writer.close()
	reader.close()


def shuffle_data(data):
	custom_print(len(data))
	# data.sort(key=lambda x: x.SrcLen)
	num_batch = int(len(data) / batch_size)
	rand_idx = random.sample(range(num_batch), num_batch)
	new_data = []
	for idx in rand_idx:
		new_data += data[batch_size * idx: batch_size * (idx + 1)]
	if len(new_data) < len(data):
		new_data += data[num_batch * batch_size:]
	return new_data


def get_max_len(sample_batch):
	src_max_len = len(sample_batch[0].SrcWords)
	for idx in range(1, len(sample_batch)):
		if len(sample_batch[idx].SrcWords) > src_max_len:
			src_max_len = len(sample_batch[idx].SrcWords)

	trg_max_len = len(sample_batch[0].TrgRels)
	for idx in range(1, len(sample_batch)):
		if len(sample_batch[idx].TrgRels) > trg_max_len:
			trg_max_len = len(sample_batch[idx].TrgRels)

	return src_max_len, trg_max_len


def get_words_index_seq(words, max_len):
	seq = list()
	for word in words:
		if lower_cased:
			word = word.lower()
		if word in word_vocab:
			seq.append(word_vocab[word])
		else:
			seq.append(word_vocab['<UNK>'])
	pad_len = max_len - len(words)
	for i in range(0, pad_len):
		seq.append(word_vocab['<PAD>'])
	return seq


def get_pos_index_seq(words, max_len):
	seq = list()	
	sent = " ".join(words).strip()
	doc = nlp(sent)
	tags = [tok.pos_ if tok.pos_ == 'PUNCT' else tok.pos_ + "-" + tok.tag_ for tok in doc]
	for t in tags:
		if t in pos_vocab:
			seq.append(pos_vocab[t])
		else:
			seq.append(pos_vocab['<UNK>'])
	pad_len = max_len - len(seq)
	for i in range(0, pad_len):
		seq.append(pos_vocab['<PAD>'])
	return seq


def get_dep_index_seq(words, max_len):
	seq = list()	
	sent = " ".join(words).strip()
	doc = nlp(sent)
	tags = [tok.dep_ for tok in doc]
	for t in tags:
		if t in dep_vocab:
			seq.append(dep_vocab[t])
		else:
			seq.append(dep_vocab['<UNK>'])
	pad_len = max_len - len(seq)
	for i in range(0, pad_len):
		seq.append(dep_vocab['<PAD>'])
	return seq


def get_char_seq(words, max_len):
	char_seq = list()
	for i in range(0, conv_filter_size - 1):
		char_seq.append(char_vocab['<PAD>'])
	for word in words:
		if lower_cased:
			word = word.lower()
		for c in word[0:min(len(word), max_word_len)]:
			if c in char_vocab:
				char_seq.append(char_vocab[c])
			else:
				char_seq.append(char_vocab['<UNK>'])
		pad_len = max_word_len - len(word)
		for i in range(0, pad_len):
			char_seq.append(char_vocab['<PAD>'])
		for i in range(0, conv_filter_size - 1):
			char_seq.append(char_vocab['<PAD>'])

	pad_len = max_len - len(words)
	for i in range(0, pad_len):
		for i in range(0, max_word_len + conv_filter_size - 1):
			char_seq.append(char_vocab['<PAD>'])
	return char_seq


def get_relation_index_seq(rel_ids, max_len):
	seq = list()
	for r in rel_ids:
		seq.append(r)
	seq.append(relnameToIdx['None'])
	pad_len = max_len + 1 - len(seq)
	for i in range(0, pad_len):
		seq.append(relnameToIdx['<PAD>'])
	return seq


def get_padded_pointers(pointers, pidx, max_len):
	idx_list = []
	for p in pointers:
		idx_list.append(p[pidx])
	pad_len = max_len + 1 - len(pointers)
	for i in range(0, pad_len):
		idx_list.append(-1)
	return idx_list


def get_pointer_location(pointers, pidx, src_max_len, trg_max_len):
	loc_seq = []
	for p in pointers:
		cur_seq = [0 for i in range(src_max_len)]
		cur_seq[p[pidx]] = 1
		loc_seq.append(cur_seq)
	pad_len = trg_max_len + 1 - len(pointers)
	for i in range(pad_len):
		cur_seq = [0 for i in range(src_max_len)]
		loc_seq.append(cur_seq)
	return loc_seq


def get_padded_mask(cur_len, max_len):
	mask_seq = list()
	for i in range(0, cur_len):
		mask_seq.append(0)
	pad_len = max_len - cur_len
	for i in range(0, pad_len):
		mask_seq.append(1)
	return mask_seq


def get_target_vec(pointers, rels, src_max_len):
	vec = [0 for i in range(src_max_len + len(relnameToIdx))]
	for i in range(len(pointers)):
		p = pointers[i]
		vec[p[0]] += 1
		vec[p[1]] += 1
		vec[p[2]] += 1
		vec[p[3]] += 1
		vec[src_max_len + rels[i]] += 1
	return vec


def get_batch_data(cur_samples, is_training=False):
	"""
	Returns the training samples and labels as numpy array
	"""
	batch_src_max_len, batch_trg_max_len = get_max_len(cur_samples)
	batch_trg_max_len += 1
	src_words_list = list()
	src_words_mask_list = list()
	src_char_seq = list()
	decoder_input_list = list()
	src_pos_seq = list()
	src_dep_seq = list()
	src_loc_seq = list()
	arg1sweights = []
	arg1eweights = []
	arg2sweights = []
	arg2eweights = []

	rel_seq = list()
	arg1_start_seq = list()
	arg1_end_seq = list()
	arg2_start_seq = list()
	arg2_end_seq = list()
	target_vec_seq = []
	target_vec_mask_seq = []

	for sample in cur_samples:
		src_words_list.append(get_words_index_seq(sample.SrcWords, batch_src_max_len))
		src_words_mask_list.append(get_padded_mask(sample.SrcLen, batch_src_max_len))
		src_char_seq.append(get_char_seq(sample.SrcWords, batch_src_max_len))
		src_pos_seq.append(get_pos_index_seq(sample.SrcWords, batch_src_max_len))
		src_dep_seq.append(get_dep_index_seq(sample.SrcWords, batch_src_max_len))
		src_loc_seq.append([i+1 for i in range(len(sample.SrcWords))] +
						   [0 for i in range(batch_src_max_len - len(sample.SrcWords))])

		if is_training:
			arg1_start_seq.append(get_padded_pointers(sample.TrgPointers, 0, batch_trg_max_len))
			arg1_end_seq.append(get_padded_pointers(sample.TrgPointers, 1, batch_trg_max_len))
			arg2_start_seq.append(get_padded_pointers(sample.TrgPointers, 2, batch_trg_max_len))
			arg2_end_seq.append(get_padded_pointers(sample.TrgPointers, 3, batch_trg_max_len))
			arg1sweights.append(get_pointer_location(sample.TrgPointers, 0, batch_src_max_len, batch_trg_max_len))
			arg1eweights.append(get_pointer_location(sample.TrgPointers, 1, batch_src_max_len, batch_trg_max_len))
			arg2sweights.append(get_pointer_location(sample.TrgPointers, 2, batch_src_max_len, batch_trg_max_len))
			arg2eweights.append(get_pointer_location(sample.TrgPointers, 3, batch_src_max_len, batch_trg_max_len))
			rel_seq.append(get_relation_index_seq(sample.TrgRels, batch_trg_max_len))
			decoder_input_list.append(get_relation_index_seq(sample.TrgRels, batch_trg_max_len))
			target_vec_seq.append(get_target_vec(sample.TrgPointers, sample.TrgRels, batch_src_max_len))
			target_vec_mask_seq.append([0 for i in range(len(sample.TrgRels))] +
									   [1 for i in range(batch_trg_max_len + 1 - len(sample.TrgRels))])
		else:
			decoder_input_list.append(get_relation_index_seq([], 1))

	return {'src_words': np.array(src_words_list, dtype=np.float32),
			'src_words_mask': np.array(src_words_mask_list),
			'src_chars': np.array(src_char_seq),
			'src_pos_tags': np.array(src_pos_seq),
			'src_dep_tags': np.array(src_dep_seq),
			'src_loc': np.array(src_loc_seq),
			'decoder_input': np.array(decoder_input_list),
			'arg1sweights': np.array(arg1sweights),
			'arg1eweights': np.array(arg1eweights),
			'arg2sweights': np.array(arg2sweights),
			'arg2eweights': np.array(arg2eweights),
			'rel': np.array(rel_seq),
			'arg1_start': np.array(arg1_start_seq),
			'arg1_end': np.array(arg1_end_seq),
			'arg2_start': np.array(arg2_start_seq),
			'arg2_end': np.array(arg2_end_seq),
			'target_vec': np.array(target_vec_seq),
			'target_vec_mask': np.array(target_vec_mask_seq)}


class WordEmbeddings(nn.Module):
	def __init__(self, vocab_size, embed_dim, drop_out_rate):
		super(WordEmbeddings, self).__init__()
		self.embeddings = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
		if job_mode == 'train':
			self.embeddings.weight.data.copy_(torch.from_numpy(word_embed_matrix))
		self.embeddings.weight.requires_grad = False
		self.dropout = nn.Dropout(drop_out_rate)

	def forward(self, words_seq):
		word_embeds = self.embeddings(words_seq)
		word_embeds = self.dropout(word_embeds)
		return word_embeds

	def weight(self):
		return self.embeddings.weight


class CharEmbeddings(nn.Module):
	def __init__(self, vocab_size, embed_dim, drop_out_rate):
		super(CharEmbeddings, self).__init__()
		self.embeddings = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
		self.conv1d = nn.Conv1d(char_embed_dim, char_feature_size, 3)
		self.max_pool = nn.MaxPool1d(max_word_len + conv_filter_size - 1, max_word_len + conv_filter_size - 1)
		self.dropout = nn.Dropout(drop_out_rate)

	def forward(self, char_seq):
		char_embeds = self.embeddings(char_seq)
		char_embeds = self.dropout(char_embeds)
		char_embeds = char_embeds.permute(0, 2, 1)
		char_feature = torch.tanh(self.max_pool(self.conv1d(char_embeds)))
		char_feature = char_feature.permute(0, 2, 1)

		return char_feature


class POSEmbeddings(nn.Module):
	def __init__(self, tag_len, tag_dim, drop_out_rate):
		super(POSEmbeddings, self).__init__()
		self.embeddings = nn.Embedding(tag_len, tag_dim, padding_idx=0)
		self.dropout = nn.Dropout(drop_out_rate)

	def forward(self, pos_seq):
		pos_embeds = self.embeddings(pos_seq)
		pos_embeds = self.dropout(pos_embeds)
		return pos_embeds


class DEPEmbeddings(nn.Module):
	def __init__(self, tag_len, tag_dim, drop_out_rate):
		super(DEPEmbeddings, self).__init__()
		self.embeddings = nn.Embedding(tag_len, tag_dim, padding_idx=0)
		self.dropout = nn.Dropout(drop_out_rate)

	def forward(self, dep_seq):
		dep_embeds = self.embeddings(dep_seq)
		dep_embeds = self.dropout(dep_embeds)
		return dep_embeds


class LocEmbeddings(nn.Module):
	def __init__(self, embed_size, embed_dim, drop_out_rate):
		super(LocEmbeddings, self).__init__()
		self.embeddings = nn.Embedding(embed_size, embed_dim, padding_idx=0)
		self.dropout = nn.Dropout(drop_out_rate)

	def forward(self, loc_seq):
		loc_embeds = self.embeddings(loc_seq)
		loc_embeds = self.dropout(loc_embeds)
		return loc_embeds


class Attention(nn.Module):
	def __init__(self, input_dim):
		super(Attention, self).__init__()
		self.input_dim = input_dim
		self.linear_ctx = nn.Linear(self.input_dim, self.input_dim, bias=False)
		self.linear_query = nn.Linear(self.input_dim, self.input_dim, bias=True)
		self.v = nn.Linear(self.input_dim, 1)

	def forward(self, s_prev, enc_hs, src_mask):
		uh = self.linear_ctx(enc_hs)
		wq = self.linear_query(s_prev)
		wquh = torch.tanh(wq + uh)
		attn_weights = self.v(wquh).squeeze()
		attn_weights.data.masked_fill_(src_mask.data, -float('inf'))
		attn_weights = F.softmax(attn_weights, dim=-1)
		ctx = torch.bmm(attn_weights.unsqueeze(1), enc_hs).squeeze()
		return ctx, attn_weights


class Sentiment_Attention_(nn.Module):
	def __init__(self, enc_hid_dim, arg_dim):
		super(Sentiment_Attention_, self).__init__()
		self.w1 = nn.Linear(enc_hid_dim + arg_dim, 1)
		self.w2 = nn.Linear(enc_hid_dim + arg_dim, 1)

	def forward(self, arg1, arg2, enc_hs, src_mask):
		ctx_arg1 = torch.cat((enc_hs, arg1.unsqueeze(1).repeat(1, enc_hs.size()[1], 1)), -1)
		ctx_arg1_att = self.w1(ctx_arg1).squeeze()
		ctx_arg1_att.data.masked_fill_(src_mask.data, -float('inf'))
		ctx_arg1_att = F.softmax(ctx_arg1_att, dim=-1)
		ctx1 = torch.bmm(ctx_arg1_att.unsqueeze(1), enc_hs).squeeze()

		ctx_arg2 = torch.cat((enc_hs, arg2.unsqueeze(1).repeat(1, enc_hs.size()[1], 1)), -1)
		ctx_arg2_att = self.w2(ctx_arg2).squeeze()
		ctx_arg2_att.data.masked_fill_(src_mask.data, -float('inf'))
		ctx_arg2_att = F.softmax(ctx_arg2_att, dim=-1)
		ctx2 = torch.bmm(ctx_arg2_att.unsqueeze(1), enc_hs).squeeze()

		return torch.cat((ctx1, ctx2), -1)


class Sentiment_Attention(nn.Module):
	def __init__(self, enc_hid_dim, arg_dim):
		super(Sentiment_Attention, self).__init__()
		self.w1 = nn.Linear(enc_hid_dim, arg_dim)
		self.w2 = nn.Linear(enc_hid_dim, arg_dim)

	def forward(self, arg1, arg2, enc_hs, src_mask):
		ctx_arg1_att = torch.bmm(torch.tanh(self.w1(enc_hs)), arg1.unsqueeze(2)).squeeze()
		ctx_arg1_att.data.masked_fill_(src_mask.data, -float('inf'))
		ctx_arg1_att = F.softmax(ctx_arg1_att, dim=-1)
		ctx1 = torch.bmm(ctx_arg1_att.unsqueeze(1), enc_hs).squeeze()

		ctx_arg2_att = torch.bmm(torch.tanh(self.w2(enc_hs)), arg2.unsqueeze(2)).squeeze()
		ctx_arg2_att.data.masked_fill_(src_mask.data, -float('inf'))
		ctx_arg2_att = F.softmax(ctx_arg2_att, dim=-1)
		ctx2 = torch.bmm(ctx_arg2_att.unsqueeze(1), enc_hs).squeeze()

		return torch.cat((ctx1, ctx2), -1)


def get_vec(arg1s, arg1e, arg2s, arg2e, rel):
	arg1svec = F.softmax(arg1s, dim=-1)
	arg1evec = F.softmax(arg1e, dim=-1)
	arg2svec = F.softmax(arg2s, dim=-1)
	arg2evec = F.softmax(arg2e, dim=-1)
	relvec = F.softmax(rel, dim=-1)
	argvec = arg1svec + arg1evec + arg2svec + arg2evec
	argvec = torch.cat((argvec, relvec), -1)
	return argvec


class Encoder(nn.Module):
	def __init__(self, input_dim, hidden_dim, layers, is_bidirectional, drop_out_rate):
		super(Encoder, self).__init__()
		self.input_dim = input_dim
		self.hidden_dim = hidden_dim
		self.layers = layers
		self.is_bidirectional = is_bidirectional
		self.drop_rate = drop_out_rate
		self.word_embeddings = WordEmbeddings(len(word_vocab), word_embed_dim, drop_rate)
		if use_char_embed:
			self.char_embeddings = CharEmbeddings(len(char_vocab), char_embed_dim, drop_rate)
		if use_pos_tags:
			self.pos_embeddings = POSEmbeddings(len(pos_vocab), pos_tag_dim, drop_rate)
		if use_dep_tags:
			self.dep_embeddings = DEPEmbeddings(len(dep_vocab), dep_tag_dim, drop_rate)
		if use_loc_embed:
			self.loc_embeddings = LocEmbeddings(max_src_len + 1, loc_embed_dim, drop_rate)
		if enc_type == 'LSTM':
			self.lstm = nn.LSTM(self.input_dim, self.hidden_dim, self.layers, batch_first=True,
								bidirectional=self.is_bidirectional, dropout=drop_out_rate)

		self.dropout = nn.Dropout(self.drop_rate)

	def forward(self, words, chars, pos_seq, dep_seq, loc_seq, adv=None, is_training=False):
		src_word_embeds = self.word_embeddings(words)
		if adv is not None:
			batch_len = src_word_embeds.size()[0]
			seq_len = src_word_embeds.size()[1]
			adv = adv.unsqueeze(0).repeat(batch_len, 1, 1)
			adv = torch.index_select(adv.view(-1, word_embed_dim), 0,
									 words.data.view(-1)).view(batch_len, seq_len, -1)
			src_word_embeds.data = src_word_embeds.data + adv

		words_input = src_word_embeds
		if use_char_embed:
			char_feature = self.char_embeddings(chars)
			words_input = torch.cat((words_input, char_feature), -1)
		if use_pos_tags:
			src_pos_embeds = self.pos_embeddings(pos_seq)
			words_input = torch.cat((words_input, src_pos_embeds), -1)
		if use_dep_tags:
			src_dep_embeds = self.dep_embeddings(dep_seq)
			words_input = torch.cat((words_input, src_dep_embeds), -1)
		if use_loc_embed:
			src_loc_embeds = self.loc_embeddings(loc_seq)
			words_input = torch.cat((words_input, src_loc_embeds), -1)

		outputs, hc = self.lstm(words_input)
		outputs = self.dropout(outputs)
		return outputs


class Decoder(nn.Module):
	def __init__(self, input_dim, hidden_dim, layers, drop_out_rate, max_length):
		super(Decoder, self).__init__()
		self.input_dim = input_dim
		self.hidden_dim = hidden_dim
		self.layers = layers
		self.drop_rate = drop_out_rate
		self.max_length = max_length

		if att_type == 0:
			self.attention = Attention(input_dim)
			self.lstm = nn.LSTMCell(rel_embed_dim + 4 * pointer_net_hidden_size + enc_hidden_size,
									self.hidden_dim)
		elif att_type == 1:
			self.w = nn.Linear(9 * self.input_dim, self.input_dim)
			self.attention = Attention(input_dim)
			self.lstm = nn.LSTMCell(10 * self.input_dim, self.hidden_dim)
		else:
			self.w = nn.Linear(4 * pointer_net_hidden_size, self.input_dim)
			self.attention1 = Attention(input_dim)
			self.attention2 = Attention(input_dim)
			self.lstm = nn.LSTMCell(4 * pointer_net_hidden_size + 2 * enc_hidden_size,
									self.hidden_dim)

		if gen_direct == gen_directions[0] or gen_direct == gen_directions[2]:
			self.ap_first_pointer_lstm = nn.LSTM(enc_hidden_size + dec_hidden_size, int(pointer_net_hidden_size / 2),
										   1, batch_first=True, bidirectional=True)
			self.op_second_pointer_lstm = nn.LSTM(enc_hidden_size + dec_hidden_size + pointer_net_hidden_size,
										   int(pointer_net_hidden_size / 2), 1, batch_first=True, bidirectional=True)
		if gen_direct == gen_directions[1] or gen_direct == gen_directions[2]:
			self.op_first_pointer_lstm = nn.LSTM(enc_hidden_size + dec_hidden_size, int(pointer_net_hidden_size / 2),
										   1, batch_first=True, bidirectional=True)
			self.ap_second_pointer_lstm = nn.LSTM(enc_hidden_size + dec_hidden_size + pointer_net_hidden_size,
										   int(pointer_net_hidden_size / 2), 1, batch_first=True, bidirectional=True)

		self.ap_start_lin = nn.Linear(pointer_net_hidden_size, 1)
		self.ap_end_lin = nn.Linear(pointer_net_hidden_size, 1)
		self.op_start_lin = nn.Linear(pointer_net_hidden_size, 1)
		self.op_end_lin = nn.Linear(pointer_net_hidden_size, 1)
		# self.sent_cnn = cnn()
		if use_sentiment_attention:
			self.sent_att = Sentiment_Attention(enc_hidden_size, 2 * pointer_net_hidden_size)
			self.sent_lin = nn.Linear(dec_hidden_size + 4 * pointer_net_hidden_size + 2 * enc_hidden_size,
									 len(relnameToIdx))
		else:
			self.sent_lin = nn.Linear(dec_hidden_size + 4 * pointer_net_hidden_size, len(relnameToIdx))
		self.dropout = nn.Dropout(self.drop_rate)

	def forward(self, prev_tuples, h_prev, enc_hs, src_mask, ap_start_wts, ap_end_wts, op_start_wts, op_end_wts,
				is_training=False):
		src_time_steps = enc_hs.size()[1]

		if att_type == 0:
			ctx, attn_weights = self.attention(h_prev[0].squeeze().unsqueeze(1).repeat(1, src_time_steps, 1),
												enc_hs, src_mask)
		elif att_type == 1:
			reduce_prev_tuples = self.w(prev_tuples)
			ctx, attn_weights = self.attention(reduce_prev_tuples.unsqueeze(1).repeat(1, src_time_steps, 1),
												enc_hs, src_mask)
		else:
			ctx1, attn_weights1 = self.attention1(h_prev[0].squeeze().unsqueeze(1).repeat(1, src_time_steps, 1),
											   enc_hs, src_mask)
			reduce_prev_tuples = self.w(prev_tuples)
			ctx2, attn_weights2 = self.attention2(reduce_prev_tuples.unsqueeze(1).repeat(1, src_time_steps, 1),
											   enc_hs, src_mask)
			ctx = torch.cat((ctx1, ctx2), -1)
			attn_weights = (attn_weights1 + attn_weights2) / 2

		s_cur = torch.cat((prev_tuples, ctx), 1)
		hidden, cell_state = self.lstm(s_cur, h_prev)
		hidden = self.dropout(hidden)

		if gen_direct == gen_directions[0] or gen_direct == gen_directions[2]:
			ap_first_pointer_lstm_input = torch.cat((enc_hs, hidden.unsqueeze(1).repeat(1, src_time_steps, 1)), 2)
			ap_first_pointer_lstm_out, phc = self.ap_first_pointer_lstm(ap_first_pointer_lstm_input)
			ap_first_pointer_lstm_out = self.dropout(ap_first_pointer_lstm_out)

			op_second_pointer_lstm_input = torch.cat((ap_first_pointer_lstm_input, ap_first_pointer_lstm_out), 2)
			op_second_pointer_lstm_out, phc = self.op_second_pointer_lstm(op_second_pointer_lstm_input)
			op_second_pointer_lstm_out = self.dropout(op_second_pointer_lstm_out)

		if gen_direct == gen_directions[1] or gen_direct == gen_directions[2]:
			op_first_pointer_lstm_input = torch.cat((enc_hs, hidden.unsqueeze(1).repeat(1, src_time_steps, 1)), 2)
			op_first_pointer_lstm_out, phc = self.op_first_pointer_lstm(op_first_pointer_lstm_input)
			op_first_pointer_lstm_out = self.dropout(op_first_pointer_lstm_out)

			ap_second_pointer_lstm_input = torch.cat((op_first_pointer_lstm_input, op_first_pointer_lstm_out), 2)
			ap_second_pointer_lstm_out, phc = self.ap_second_pointer_lstm(ap_second_pointer_lstm_input)
			ap_second_pointer_lstm_out = self.dropout(ap_second_pointer_lstm_out)

		if gen_direct == gen_directions[0]:
			ap_pointer_lstm_out = ap_first_pointer_lstm_out
			op_pointer_lstm_out = op_second_pointer_lstm_out
		elif gen_direct == gen_directions[1]:
			ap_pointer_lstm_out = ap_second_pointer_lstm_out
			op_pointer_lstm_out = op_first_pointer_lstm_out
		else:
			ap_pointer_lstm_out = (ap_first_pointer_lstm_out + ap_second_pointer_lstm_out)/2
			op_pointer_lstm_out = (op_first_pointer_lstm_out + op_second_pointer_lstm_out)/2

		ap_start = self.ap_start_lin(ap_pointer_lstm_out).squeeze()
		ap_start.data.masked_fill_(src_mask.data, -float('inf'))

		ap_end = self.ap_end_lin(ap_pointer_lstm_out).squeeze()
		ap_end.data.masked_fill_(src_mask.data, -float('inf'))

		ap_start_weights = F.softmax(ap_start, dim=-1)
		ap_end_weights = F.softmax(ap_end, dim=-1)

		ap_sv = torch.bmm(ap_start_weights.unsqueeze(1), ap_pointer_lstm_out).squeeze()
		ap_ev = torch.bmm(ap_end_weights.unsqueeze(1), ap_pointer_lstm_out).squeeze()
		ap = torch.cat((ap_sv, ap_ev), -1)

		op_start = self.op_start_lin(op_pointer_lstm_out).squeeze()
		op_start.data.masked_fill_(src_mask.data, -float('inf'))

		op_end = self.op_end_lin(op_pointer_lstm_out).squeeze()
		op_end.data.masked_fill_(src_mask.data, -float('inf'))

		op_start_weights = F.softmax(op_start, dim=-1)
		op_end_weights = F.softmax(op_end, dim=-1)

		op_sv = torch.bmm(op_start_weights.unsqueeze(1), op_pointer_lstm_out).squeeze()
		op_ev = torch.bmm(op_end_weights.unsqueeze(1), op_pointer_lstm_out).squeeze()
		op = torch.cat((op_sv, op_ev), -1)
		if use_sentiment_attention:
			sent_ctx = self.sent_att(ap, op, enc_hs, src_mask)
			sentiment = self.sent_lin(self.dropout(torch.cat((hidden, ap, op, sent_ctx), -1)))
		else:
			sentiment = self.sent_lin(self.dropout(torch.cat((hidden, ap, op), -1)))
		if is_training:
			pred_vec = get_vec(ap_start, ap_end, op_start, op_end, sentiment)
			ap_start = F.log_softmax(ap_start, dim=-1)
			ap_end = F.log_softmax(ap_end, dim=-1)
			op_start = F.log_softmax(op_start, dim=-1)
			op_end = F.log_softmax(op_end, dim=-1)
			sentiment = F.log_softmax(sentiment, dim=-1)
			if use_gold_location:
				ap_sv = torch.bmm(ap_start_wts.unsqueeze(1), ap_pointer_lstm_out).squeeze()
				ap_ev = torch.bmm(ap_end_wts.unsqueeze(1), ap_pointer_lstm_out).squeeze()
				ap = torch.cat((ap_sv, ap_ev), -1)

				op_sv = torch.bmm(op_start_wts.unsqueeze(1), op_pointer_lstm_out).squeeze()
				op_ev = torch.bmm(op_end_wts.unsqueeze(1), op_pointer_lstm_out).squeeze()
				op = torch.cat((op_sv, op_ev), -1)

			return sentiment.unsqueeze(1), ap_start.unsqueeze(1), ap_end.unsqueeze(1), op_start.unsqueeze(1), \
				op_end.unsqueeze(1), (hidden, cell_state), ap, op, pred_vec
		else:
			ap_start = F.softmax(ap_start, dim=-1)
			ap_end = F.softmax(ap_end, dim=-1)
			op_start = F.softmax(op_start, dim=-1)
			op_end = F.softmax(op_end, dim=-1)
			sentiment = F.softmax(sentiment, dim=-1)
			return sentiment.unsqueeze(1), ap_start.unsqueeze(1), ap_end.unsqueeze(1), op_start.unsqueeze(1), \
				   op_end.unsqueeze(1), (hidden, cell_state), ap, op


class Seq2SeqModel(nn.Module):
	def __init__(self):
		super(Seq2SeqModel, self).__init__()
		self.encoder = Encoder(enc_inp_size, int(enc_hidden_size/2), 1, True, drop_rate)
		self.decoder = Decoder(dec_inp_size, dec_hidden_size, 1, drop_rate, max_trg_len)
		self.dropout = nn.Dropout(drop_rate)

	def forward(self, src_words_seq, src_mask, src_char_seq, pos_seq, dep_seq, loc_seq, trg_words_seq, trg_seq_len,
				arg1swts, arg1ewts, arg2swts, arg2ewts, adv=None, is_training=False):
		
		batch_len = src_words_seq.size()[0]
		src_seq_len = src_words_seq.size()[1]
		
		enc_hs = self.encoder(src_words_seq, src_char_seq, pos_seq, dep_seq, loc_seq, adv, is_training)

		h0 = autograd.Variable(torch.FloatTensor(torch.zeros(batch_len, dec_hidden_size))).cuda(gpu_id)
		c0 = autograd.Variable(torch.FloatTensor(torch.zeros(batch_len, dec_hidden_size))).cuda(gpu_id)
		dec_hid = (h0, c0)

		arg1 = autograd.Variable(torch.FloatTensor(torch.zeros(batch_len, 2 * pointer_net_hidden_size))).cuda(gpu_id)
		arg2 = autograd.Variable(torch.FloatTensor(torch.zeros(batch_len, 2 * pointer_net_hidden_size))).cuda(gpu_id)

		prev_tuples = torch.cat((arg1, arg2), -1)

		if is_training:
			dec_outs = self.decoder(prev_tuples, dec_hid, enc_hs, src_mask,
									arg1swts[:, 0, :].squeeze(), arg1ewts[:, 0, :].squeeze(),
									arg2swts[:, 0, :].squeeze(), arg2ewts[:, 0, :].squeeze(), is_training)
			pred_vec = dec_outs[8].unsqueeze(1)
		else:
			dec_outs = self.decoder(prev_tuples, dec_hid, enc_hs, src_mask, None, None, None, None, is_training)
		rel = dec_outs[0]
		arg1s = dec_outs[1]
		arg1e = dec_outs[2]
		arg2s = dec_outs[3]
		arg2e = dec_outs[4]
		dec_hid = dec_outs[5]
		arg1 = dec_outs[6]
		arg2 = dec_outs[7]

		topv, topi = rel[:, :, 1:].topk(1)
		topi = torch.add(topi, 1)

		for t in range(1, trg_seq_len):
			if is_training:
				prev_tuples = torch.cat((arg1, arg2), -1) + prev_tuples
				dec_outs = self.decoder(prev_tuples / (t+1), dec_hid, enc_hs, src_mask,
										arg1swts[:, t, :].squeeze(), arg1ewts[:, t, :].squeeze(),
										arg2swts[:, t, :].squeeze(), arg2ewts[:, t, :].squeeze(), is_training)
				pred_vec = torch.cat((pred_vec, dec_outs[8].unsqueeze(1)), 1)
			else:
				prev_tuples = torch.cat((arg1, arg2), -1) + prev_tuples
				dec_outs = self.decoder(prev_tuples / (t+1), dec_hid, enc_hs, src_mask,
										None, None, None, None, is_training)

			cur_rel = dec_outs[0]
			cur_arg1s = dec_outs[1]
			cur_arg1e = dec_outs[2]
			cur_arg2s = dec_outs[3]
			cur_arg2e = dec_outs[4]
			dec_hid = dec_outs[5]
			arg1 = dec_outs[6]
			arg2 = dec_outs[7]

			rel = torch.cat((rel, cur_rel), 1)
			arg1s = torch.cat((arg1s, cur_arg1s), 1)
			arg1e = torch.cat((arg1e, cur_arg1e), 1)
			arg2s = torch.cat((arg2s, cur_arg2s), 1)
			arg2e = torch.cat((arg2e, cur_arg2e), 1)

			topv, topi = cur_rel[:, :, 1:].topk(1)
			topi = torch.add(topi, 1)

		if is_training:
			rel = rel.view(-1, len(relnameToIdx))
			arg1s = arg1s.view(-1, src_seq_len)
			arg1e = arg1e.view(-1, src_seq_len)
			arg2s = arg2s.view(-1, src_seq_len)
			arg2e = arg2e.view(-1, src_seq_len)
			return rel, arg1s, arg1e, arg2s, arg2e, pred_vec
		else:
			return rel, arg1s, arg1e, arg2s, arg2e


def get_model(model_id):
	if model_id == 1:
		return Seq2SeqModel()


def set_random_seeds(seed):
	random.seed(seed)
	np.random.seed(seed)
	torch.manual_seed(seed)
	# if n_gpu > 1:
	#     torch.cuda.manual_seed_all(seed)


def predict(samples, model, model_id):
	pred_batch_size = batch_size
	batch_count = math.ceil(len(samples) / pred_batch_size)
	move_last_batch = False
	if len(samples) - batch_size * (batch_count - 1) == 1:
		move_last_batch = True
		batch_count -= 1
	rel = list()
	arg1s = list()
	arg1e = list()
	arg2s = list()
	arg2e = list()
	model.eval()
	set_random_seeds(random_seed)
	start_time = datetime.datetime.now()
	for batch_idx in tqdm(range(0, batch_count)):
		batch_start = batch_idx * pred_batch_size
		batch_end = min(len(samples), batch_start + pred_batch_size)
		if batch_idx == batch_count - 1 and move_last_batch:
			batch_end = len(samples)

		cur_batch = samples[batch_start:batch_end]
		cur_samples_input = get_batch_data(cur_batch, False)

		src_words_seq = torch.from_numpy(cur_samples_input['src_words'].astype('long'))
		src_words_mask = torch.from_numpy(cur_samples_input['src_words_mask'].astype('bool'))
		trg_words_seq = torch.from_numpy(cur_samples_input['decoder_input'].astype('long'))
		src_chars_seq = torch.from_numpy(cur_samples_input['src_chars'].astype('long'))
		src_pos_tags = torch.from_numpy(cur_samples_input['src_pos_tags'].astype('long'))
		src_dep_tags = torch.from_numpy(cur_samples_input['src_dep_tags'].astype('long'))
		src_loc = torch.from_numpy(cur_samples_input['src_loc'].astype('long'))

		src_words_seq = autograd.Variable(src_words_seq.cuda(gpu_id))
		src_words_mask = autograd.Variable(src_words_mask.cuda(gpu_id))
		trg_words_seq = autograd.Variable(trg_words_seq.cuda(gpu_id))
		src_chars_seq = autograd.Variable(src_chars_seq.cuda(gpu_id))
		src_pos_tags = autograd.Variable(src_pos_tags.cuda(gpu_id))
		src_dep_tags = autograd.Variable(src_dep_tags.cuda(gpu_id))
		src_loc = autograd.Variable(src_loc.cuda(gpu_id))

		with torch.no_grad():
			if model_id == 1:
				outputs = model(src_words_seq, src_words_mask, src_chars_seq, src_pos_tags, src_dep_tags, src_loc,
								trg_words_seq, max_trg_len, None, None, None, None, None, False)

		rel += list(outputs[0].data.cpu().numpy())
		arg1s += list(outputs[1].data.cpu().numpy())
		arg1e += list(outputs[2].data.cpu().numpy())
		arg2s += list(outputs[3].data.cpu().numpy())
		arg2e += list(outputs[4].data.cpu().numpy())
		model.zero_grad()

	end_time = datetime.datetime.now()
	custom_print('Prediction time:', end_time - start_time)
	return rel, arg1s, arg1e, arg2s, arg2e


def train_model(model_id, train_samples, dev_samples, test_samples, test_gt_lines, best_model_file):
	train_size = len(train_samples)
	batch_count = int(math.ceil(train_size/batch_size))
	move_last_batch = False
	if len(train_samples) - batch_size * (batch_count - 1) == 1:
		move_last_batch = True
		batch_count -= 1
	custom_print("Batch Count: ", batch_count)

	model = get_model(model_id)
	pytorch_total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
	custom_print('Parameters size:', pytorch_total_params)

	if torch.cuda.is_available():
		model.cuda(gpu_id)
	# if n_gpu > 1:
	# 	model = torch.nn.DataParallel(model)

	rel_criterion = nn.NLLLoss(ignore_index=0)
	pointer_criterion = nn.NLLLoss(ignore_index=-1)
	vec_criterion = nn.MSELoss()

	custom_print('weight factor:', wf)
	optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=0.00001)
	custom_print(optimizer)

	best_dev_acc = -1.0
	best_epoch_idx = -1
	best_epoch_seed = -1
	best_p = 0
	best_r = 0
	best_f1 = 0
	best_test_p = 0
	best_test_r = 0
	best_test_f1 = -1.0
	best_test_epoch = -1

	for epoch_idx in range(0, num_epoch):
		model.train()
		model.zero_grad()
		custom_print('Epoch:', epoch_idx + 1)
		cur_seed = random_seed + epoch_idx + 1

		set_random_seeds(cur_seed)
		random.shuffle(train_samples)
		start_time = datetime.datetime.now()
		train_loss_val = 0.0

		for batch_idx in tqdm(range(0, batch_count)):
			batch_start = batch_idx * batch_size
			batch_end = min(len(train_samples), batch_start + batch_size)
			if batch_idx == batch_count - 1 and move_last_batch:
				batch_end = len(train_samples)

			cur_batch = train_samples[batch_start:batch_end]
			cur_samples_input = get_batch_data(cur_batch, True)

			src_words_seq = torch.from_numpy(cur_samples_input['src_words'].astype('long'))
			src_words_mask = torch.from_numpy(cur_samples_input['src_words_mask'].astype('bool'))
			trg_words_seq = torch.from_numpy(cur_samples_input['decoder_input'].astype('long'))
			src_chars_seq = torch.from_numpy(cur_samples_input['src_chars'].astype('long'))
			src_pos_tags = torch.from_numpy(cur_samples_input['src_pos_tags'].astype('long'))
			src_dep_tags = torch.from_numpy(cur_samples_input['src_dep_tags'].astype('long'))
			src_loc = torch.from_numpy(cur_samples_input['src_loc'].astype('long'))

			arg1sweights = torch.from_numpy(cur_samples_input['arg1sweights'].astype('float32'))
			arg1eweights = torch.from_numpy(cur_samples_input['arg1eweights'].astype('float32'))
			arg2sweights = torch.from_numpy(cur_samples_input['arg2sweights'].astype('float32'))
			arg2eweights = torch.from_numpy(cur_samples_input['arg2eweights'].astype('float32'))

			rel = torch.from_numpy(cur_samples_input['rel'].astype('long'))
			arg1s = torch.from_numpy(cur_samples_input['arg1_start'].astype('long'))
			arg1e = torch.from_numpy(cur_samples_input['arg1_end'].astype('long'))
			arg2s = torch.from_numpy(cur_samples_input['arg2_start'].astype('long'))
			arg2e = torch.from_numpy(cur_samples_input['arg2_end'].astype('long'))
			trg_vec = torch.from_numpy(cur_samples_input['target_vec'].astype('float32'))
			trg_vec_mask = torch.from_numpy(cur_samples_input['target_vec_mask'].astype('bool'))

			src_words_seq = autograd.Variable(src_words_seq.cuda(gpu_id))
			src_words_mask = autograd.Variable(src_words_mask.cuda(gpu_id))
			trg_words_seq = autograd.Variable(trg_words_seq.cuda(gpu_id))
			src_chars_seq = autograd.Variable(src_chars_seq.cuda(gpu_id))
			src_pos_tags = autograd.Variable(src_pos_tags.cuda(gpu_id))
			src_dep_tags = autograd.Variable(src_dep_tags.cuda(gpu_id))
			src_loc = autograd.Variable(src_loc.cuda(gpu_id))

			arg1sweights = autograd.Variable(arg1sweights.cuda(gpu_id))
			arg1eweights = autograd.Variable(arg1eweights.cuda(gpu_id))
			arg2sweights = autograd.Variable(arg2sweights.cuda(gpu_id))
			arg2eweights = autograd.Variable(arg2eweights.cuda(gpu_id))

			rel = autograd.Variable(rel.cuda(gpu_id))
			arg1s = autograd.Variable(arg1s.cuda(gpu_id))
			arg1e = autograd.Variable(arg1e.cuda(gpu_id))
			arg2s = autograd.Variable(arg2s.cuda(gpu_id))
			arg2e = autograd.Variable(arg2e.cuda(gpu_id))
			trg_vec = autograd.Variable(trg_vec.cuda(gpu_id))
			trg_vec_mask = autograd.Variable(trg_vec_mask.cuda(gpu_id))
			trg_seq_len = rel.size()[1]
			if model_id == 1:
				outputs = model(src_words_seq, src_words_mask, src_chars_seq, src_pos_tags, src_dep_tags, src_loc,
								trg_words_seq, trg_seq_len, arg1sweights, arg1eweights, arg2sweights,
								arg2eweights, None, True)

			rel = rel.view(-1, 1).squeeze()
			arg1s = arg1s.view(-1, 1).squeeze()
			arg1e = arg1e.view(-1, 1).squeeze()
			arg2s = arg2s.view(-1, 1).squeeze()
			arg2e = arg2e.view(-1, 1).squeeze()
			outputs[5].data.masked_fill_(trg_vec_mask.unsqueeze(2).data, 0)
			pred_vec = torch.sum(outputs[5], 1)

			loss = rel_criterion(outputs[0], rel) + \
				   wf * (pointer_criterion(outputs[1], arg1s) + pointer_criterion(outputs[2], arg1e)) + \
				   wf * (pointer_criterion(outputs[3], arg2s) + pointer_criterion(outputs[4], arg2e))

			loss.backward()
			torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
			optimizer.step()
			model.zero_grad()
			train_loss_val += loss.item()

		train_loss_val /= batch_count
		
		end_time = datetime.datetime.now()
		custom_print('Training loss:', train_loss_val)
		custom_print('Training time:', end_time - start_time)

		custom_print('\nDev Results\n')
		set_random_seeds(random_seed)
		dev_preds = predict(dev_samples, model, model_id)

		pred_pos, gt_pos, correct_pos = get_F1(dev_samples, dev_preds)
		custom_print(pred_pos, '\t', gt_pos, '\t', correct_pos)
		dev_p = float(correct_pos) / (pred_pos + 1e-8)
		dev_r = float(correct_pos) / (gt_pos + 1e-8)
		dev_acc = (2 * dev_p * dev_r) / (dev_p + dev_r + 1e-8)
		custom_print('Dev P:', round(dev_p, 3))
		custom_print('Dev R:', round(dev_r, 3))
		custom_print('Dev F1:', round(dev_acc, 3))

		custom_print('\nTest Results\n')
		set_random_seeds(random_seed)
		test_preds = predict(test_samples, model, model_id)

		pred_pos, gt_pos, correct_pos = get_F1(test_samples, test_preds)
		custom_print(pred_pos, '\t', gt_pos, '\t', correct_pos)
		test_p = float(correct_pos) / (pred_pos + 1e-8)
		test_r = float(correct_pos) / (gt_pos + 1e-8)
		test_acc = (2 * test_p * test_r) / (test_p + test_r + 1e-8)
		custom_print('Test P:', round(test_p, 3))
		custom_print('Test R:', round(test_r, 3))
		custom_print('Test F1:', round(test_acc, 3))

		if test_acc >= best_test_f1:
			best_test_epoch = epoch_idx + 1
			best_test_f1 = test_acc
			best_test_p = test_p
			best_test_r = test_r

		if dev_acc >= best_dev_acc:
			best_epoch_idx = epoch_idx + 1
			best_epoch_seed = cur_seed
			best_p = test_p
			best_r = test_r
			best_f1 = test_acc
			best_test_preds = test_preds
			custom_print('model saved......')
			best_dev_acc = dev_acc
			# torch.save(model.state_dict(), best_model_file)		

		custom_print('\n\n')
		if epoch_idx + 1 - best_epoch_idx >= early_stop_cnt:
			break

	custom_print('*******')
	custom_print('Best Epoch:', best_epoch_idx)
	custom_print('Best Epoch Seed:', best_epoch_seed)
	custom_print('Corresponding P:', round(best_p, 3))
	custom_print('Corresponding R:', round(best_r, 3))
	custom_print('Corresponding F1:', round(best_f1, 3))
	custom_print('\n\n')
	custom_print('Best Test Epoch:', best_test_epoch)
	custom_print('Corresponding P:', round(best_test_p, 3))
	custom_print('Corresponding R:', round(best_test_r, 3))
	custom_print('Corresponding F1:', round(best_test_f1, 3))
	custom_print('\n\n')

	print('Test size:', len(test_samples))
	get_splitted_F1(test_samples, best_test_preds)
	write_test_res(src_test_file, test_gt_lines, test_samples, best_test_preds, os.path.join(trg_data_folder, 'test.out'))


if __name__ == "__main__":
	os.environ['CUDA_VISIBLE_DEVICES'] = sys.argv[1]
	gpu_id = int(sys.argv[1])
	random_seed = int(sys.argv[2])
	# n_gpu = torch.cuda.device_count()
	set_random_seeds(random_seed)

	src_data_folder = sys.argv[3]
	trg_data_folder = sys.argv[4].strip().split('/')[0] + "/" + str(random_seed) + "_" + sys.argv[4].strip().split('/')[1]
	
	model_name = 1
	job_mode = sys.argv[5]

	batch_size = int(sys.argv[6])
	num_epoch = int(sys.argv[7])
	early_stop_cnt = int(sys.argv[8])
	drop_rate = 0.5
	
	use_char_embed = False
	use_pos_tags = True
	use_dep_tags = True

	use_loc_embed = False
	use_sentiment_attention = False

	use_nr_triplets = False
	use_data_aug = False
	lower_cased = False

	gen_directions = ['AspectFirst', 'OpinionFirst', 'BothWays']
	gen_direct = sys.argv[9]
	trg_data_folder += "_" + gen_direct
	gen_direct = gen_directions[0] if gen_direct == 'AF' else (gen_directions[1] if gen_direct == 'OF' else gen_directions[2])
	triplet_orders = ['Random', 'AP_OP', 'OP_AP']
	trip_order = sys.argv[10]
	trg_data_folder += "_" + trip_order
	trip_order = triplet_orders[0] if trip_order == 'R' else (triplet_orders[1] if trip_order == 'AP' else triplet_orders[2])
	if not os.path.exists(trg_data_folder):
		os.mkdir(trg_data_folder)
		
	use_gold_location = False

	max_src_len = 100
	max_trg_len = 10
	max_nr_cnt = 10
	if use_nr_triplets:
		max_trg_len += max_nr_cnt
	embedding_file = 'cased_glove300.txt'
	
	wf = 1
	att_type = 2

	enc_type = 'LSTM'

	word_embed_dim = 300
	word_min_freq = 10

	char_embed_dim = 25
	pos_tag_dim = 50
	dep_tag_dim = 50
	char_feature_size = 25
	conv_filter_size = 3
	max_word_len = 25

	loc_embed_dim = 25
	rel_embed_dim = 25

	enc_inp_size = word_embed_dim
	if use_char_embed:
		enc_inp_size += char_feature_size
	if use_pos_tags:
		enc_inp_size += pos_tag_dim
	if use_dep_tags:
		enc_inp_size += dep_tag_dim
	if use_loc_embed:
		enc_inp_size += loc_embed_dim
	enc_hidden_size = 300
	dec_inp_size = enc_hidden_size
	dec_hidden_size = dec_inp_size
	pointer_net_hidden_size = enc_hidden_size

	Sample = recordclass("Sample", "Id SrcLen SrcWords TrgLen TrgRels TrgPointers")
	rel_file = os.path.join(src_data_folder, 'relations.txt')
	relnameToIdx, relIdxToName = get_relations(rel_file)

	if job_mode == 'train':
		logger = open(os.path.join(trg_data_folder, 'training.log'), 'w')
		custom_print(sys.argv)
		custom_print(max_src_len, '\t', max_trg_len, '\t', drop_rate, '\t', gen_direct, '\t', trip_order)
		custom_print(batch_size, '\t', num_epoch)
		custom_print(enc_type)
		custom_print('loading data......')
		model_file_name = os.path.join(trg_data_folder, 'model.h5py')

		src_train_file = os.path.join(src_data_folder, 'train.sent')
		trg_train_file = os.path.join(src_data_folder, 'train.pointer')
		train_data = read_data(src_train_file, trg_train_file, 1)

		src_dev_file = os.path.join(src_data_folder, 'dev.sent')
		trg_dev_file = os.path.join(src_data_folder, 'dev.pointer')
		dev_data = read_data(src_dev_file, trg_dev_file, 2)

		src_test_file = os.path.join(src_data_folder, 'test.sent')
		trg_test_file = os.path.join(src_data_folder, 'test.pointer')
		test_data = read_data(src_test_file, trg_test_file, 3)

		custom_print('Training data size:', len(train_data))
		custom_print('Development data size:', len(dev_data))
		custom_print('Test data size:', len(test_data))

		reader = open(os.path.join(src_data_folder, 'test.tup'))
		test_gt_lines = reader.readlines()
		reader.close()

		custom_print("preparing vocabulary......")
		save_vocab = os.path.join(trg_data_folder, 'vocab.pkl')

		custom_print("getting pos tags......")
		pos_vocab = build_pos_tags(src_train_file, src_dev_file, src_test_file)

		custom_print("getting dep tags......")
		dep_vocab = build_dep_tags(src_train_file, src_dev_file, src_test_file)

		word_vocab, char_vocab, word_embed_matrix = build_vocab(train_data, dev_data, test_data,
																save_vocab, embedding_file)

		custom_print("Training started......")
		train_model(model_name, train_data, dev_data, test_data, test_gt_lines, model_file_name)
		logger.close()

	if job_mode == 'test':
		logger = open(os.path.join(trg_data_folder, 'test.log'), 'w')
		custom_print(sys.argv)
		custom_print("loading word vectors......")
		vocab_file_name = os.path.join(trg_data_folder, 'vocab.pkl')
		word_vocab, char_vocab, pos_vocab, dep_vocab = load_vocab(vocab_file_name)

		custom_print('vocab size:', len(word_vocab))

		model_file = os.path.join(trg_data_folder, 'model.h5py')

		best_model = get_model(model_name)
		custom_print(best_model)
		if torch.cuda.is_available():
			best_model.cuda(gpu_id)
		# if n_gpu > 1:
		#     best_model = torch.nn.DataParallel(best_model)
		best_model.load_state_dict(torch.load(model_file))

		custom_print('\nTest Results\n')
		src_test_file = os.path.join(src_data_folder, 'test.sent')
		trg_test_file = os.path.join(src_data_folder, 'test.pointer')
		
		test_data = read_data(src_test_file, trg_test_file, 3)
		custom_print('Test data size:', len(test_data))

		reader = open(os.path.join(src_data_folder, 'test.tup'))
		test_gt_lines = reader.readlines()
		reader.close()

		print('Test size:', len(test_data))
		# set_random_seeds(random_seed)
		test_preds = predict(test_data, best_model, model_name)
		pred_pos, gt_pos, correct_pos = get_F1(test_data, test_preds)
		custom_print(pred_pos, '\t', gt_pos, '\t', correct_pos)
		p = float(correct_pos) / (pred_pos + 1e-8)
		r = float(correct_pos) / (gt_pos + 1e-8)
		test_acc = (2 * p * r) / (p + r + 1e-8)
		custom_print('P:', round(p, 3))
		custom_print('R:', round(r, 3))
		custom_print('F1:', round(test_acc, 3))

		write_test_res(src_test_file, test_gt_lines, test_data, test_preds,
					   os.path.join(trg_data_folder, 'test.out'))

		logger.close()

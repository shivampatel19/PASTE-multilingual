import sys
import os
from transformers import BertTokenizer
from spacyface.aligner import BertAligner

def getTokenizer(mode):
	if mode == 'gen':
		tokenizer = BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
	if mode == 'gen_mul':
		tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-uncased', do_lower_case=True)

	return tokenizer

def getAligner(mode):
	if mode == 'gen':
		alnr = BertAligner.from_pretrained("bert-base-uncased")
	if mode == 'gen_mul':
		alnr = BertAligner.from_pretrained("bert-base-multilingual-uncased")
	return alnr

def sorter(file,counts):
	fr = open(file, 'r')
	lines = fr.readlines()
	fr.close()
	ptr = 0
	lin = 0
	j=0
	fw = open(file, 'w')
	for line in lines:
		if(j<len(counts)):
			if ptr != counts[j]-1:
				lin+=1
				fw.write(line)
			else:
				j+=1
			
			ptr += 1
		elif(j==len(counts) and ptr<=len(lines)):
			lin +=1
			fw.write(line)
	print("Deleted")
	print(str(lin) + '\n\n')
	fw.close()


def getPOS_DEP(sent_file, tup_file, pointer_file, pos_out, dep_out):
	f1 = open(sent_file)
	g1 = open(pos_out,'w')
	g2 = open(dep_out,'w')

	line_count = 0
	    
	err_count = 0
	counts = []  ####CHANGE
	for line in f1:
		line = line.strip()
		line_count += 1
		tokens = tokenizer.tokenize(line)
		features = alnr.meta_tokenize(line)
		align_tokens = [feature.token for feature in features]
		pos_tags = [feature.pos if feature.pos == 'PUNCT' else feature.pos + "-" + feature.tag for feature in features]
		dep_tags = [feature.dep for feature in features]
		if tokens == align_tokens:
			pos_tags = ' '.join(pos_tags)
			dep_tags = ' '.join(dep_tags)
			g1.write(pos_tags + '\n')
			g2.write(dep_tags + '\n')
		else:
			print(f'Counts not matching on line {line_count} in {sent_file}..')
			counts.append(line_count)  ####CHANGE
			print(line)
			print(tokens)
			print(align_tokens)
			print("\n")
			err_count += 1
	
	f1.close()
	g1.close()
	g2.close()
	
	print(counts)  ####CHANGE
	sorter(sent_file, counts)
	sorter(tup_file, counts)
	sorter(pointer_file, counts)



if __name__ == "__main__":
	mode = sys.argv[1]
	tokenizer = getTokenizer(mode)
	alnr = getAligner(mode)
	dirs = [sys.argv[2]+'/']

	for path in dirs:
		os.chdir(path)
		if mode == 'gen' or mode == 'gen_mul':
			getPOS_DEP('train.sent', 'train.tup', 'train.pointer', 'trainb_pos.sent', 'trainb_dep.sent')
			getPOS_DEP('dev.sent', 'dev.tup', 'dev.pointer', 'devb_pos.sent', 'devb_dep.sent')
			getPOS_DEP('test.sent', 'test.tup', 'test.pointer', 'testb_pos.sent', 'testb_dep.sent')
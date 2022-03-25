import sys
import os
from transformers import BertTokenizer

def getTokenizer(mode):
	if mode == 'gen':
		tokenizer = BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
	if mode == 'gen_mul':
		tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-uncased', do_lower_case=True)
	return tokenizer

def getBERTData(n1, n2, n3, m1, m2, m3):
	f1 = open(n1)
	f2 = open(n2)
	f3 = open(n3)

	g1 = open(m1,'w')
	g2 = open(m2,'w')
	g3 = open(m3,'w')

	for line in f1:
			words = line.split(' ')
			
			new = ''
			cnt = 0
			lst = []
			for word in words:
					# sentence file
					li = []
					li.append(cnt)
					# word = word.strip().lower()
					sub_tokens = tokenizer.tokenize(word)
					cnt += len(sub_tokens)
					li.append(cnt-1)
					new += ' '.join(sub_tokens)
					new += ' '
					lst.append(li)
			g1.write(new[:-1]+'\n')

			# ptr and tup file 
			words = new[:-1].split(' ')
			ptrs = f3.readline()
			ptrs = ptrs[:-1].split(' | ')
			pointer = ''
			tup = ''
			for ptr in ptrs:
					pt = ptr.split(' ')
					s1 = lst[int(pt[0])][0]
					e1 = lst[int(pt[1])][1]
					asp = ' '.join(words[s1:e1+1])
					#print(ptr)
					s1 = str(s1)
					e1 = str(e1)

					s2 = lst[int(pt[2])][0]
					e2 = lst[int(pt[3])][1]
					op = ' '.join(words[s2:e2+1])
					s2 = str(s2)
					e2 = str(e2)
					

					pointer += s1 + ' '+ e1 + ' '+ s2 + ' ' + e2 + ' '+ pt[4]+' | '
					tup += asp + ' ; ' + op + ' ; ' + pt[4] + ' | '
					
			if len(pointer)>3:
					g3.write(pointer[:-3]+'\n')
					g2.write(tup[:-3]+'\n')
			else:
					g2.write(' \n')
					g3.write(' \n') 

if __name__ == "__main__":
	mode = sys.argv[1]
	tokenizer = getTokenizer(mode)
	dirs = [sys.argv[2]+'/']


	for path in dirs:
		os.chdir(path)
		if mode == 'gen' or mode == 'gen_mul':
			getBERTData('train.sent','train.tup','train.pointer','trainb.sent','trainb.tup','trainb.pointer')
			getBERTData('dev.sent','dev.tup','dev.pointer','devb.sent','devb.tup','devb.pointer')
			getBERTData('test.sent','test.tup','test.pointer','testb.sent','testb.tup','testb.pointer')
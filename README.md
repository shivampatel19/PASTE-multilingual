# PASTE-multilingual

HOW TO USE IT:

SemEval-2022 Task 10: Structured Sentiment competition datasets was taken , which contained crosslingual and monolingual datasets in json formats.

Step 1: The datasets were converted in three files namely .sent, .tup and .pointer files for each and every language
        The json files were converted using MainConversionCode.ipynb provided in conversion directory.
        
Step 2: These datasets are then used to create additional files namely trainb.sent, train.tup and trainb.pointer from train.sent, train.tup and 
        train.pointer using prep_BERTData.py. These additional files are the tokenized files created using BertTokenizer with bert-base-uncased and
        bert-base-multilingual-uncased.
        
Step 3: We used prep_POS_DEP_forBERT.py to create POS and DEP sentence files which keeps a track of Part-Of-Speech(POS) and Dependency-Based(DEP)
        features of each word occured in the sentence files.
        
Step 4: Now all the files needed for Aspect Sentiment Triplet Extraction(Prediction) are completed and we will use all these files for training and
        testing purposes using PASTE_BERT.py file which contains PASTE model , A Pointer Network based decoding Framework of ASTE.
        The PASTE_BERT.py and error_analysis.py file are ran using the script files created for each and every language which contains different
        configurations and conditions for testing purposes.
        

import sklearn
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from lifelines import CoxPHFitter
from lifelines.utils import concordance_index as cindex
from sklearn.model_selection import train_test_split

from load import load_data
df = load_data()

print(df.shape)
df.head()

df_dev, df_test = train_test_split(df, test_size = 0.2)
df_train, df_val = train_test_split(df_dev, test_size = 0.25)

print("Total number of patients:", df.shape[0])
print("Total number of patients in training set:", df_train.shape[0])
print("Total number of patients in validation set:", df_val.shape[0])
print("Total number of patients in test set:", df_test.shape[0])

def to_one_hot(dataframe, columns):

    one_hot_df = pd.get_dummies(dataframe, columns = columns, drop_first = True, dtype=np.float64)
    return one_hot_df

to_encode = ['edema', 'stage']
one_hot_train = to_one_hot(df_train, to_encode)
one_hot_val = to_one_hot(df_val, to_encode)
one_hot_test = to_one_hot(df_test, to_encode)

print(one_hot_val.columns.tolist())
print(f"There are {len(one_hot_val.columns)} columns")

cph = CoxPHFitter()
cph.fit(one_hot_train, duration_col = 'time', event_col = 'status', step_size=0.1)
cph.print_summary()

cph.plot_covariate_groups('trt', values=[0, 1]);

def hazard_ratio(case_1, case_2, cox_params):
   
    hr = np.exp(cox_params.dot((case_1 - case_2).T))
    return hr

i = 1
case_1 = one_hot_train.iloc[i, :].drop(['time', 'status'])

j = 5
case_2 = one_hot_train.iloc[j, :].drop(['time', 'status'])

print(hazard_ratio(case_1.values, case_2.values, cph.params_.values))

def harrell_c(y_true, scores, event):
  
    n = len(y_true)
    assert (len(scores) == n and len(event) == n)
    
    concordant = 0.0
    permissible = 0.0
    ties = 0.0
    
    result = 0.0
    
    for i in range(n):
      for j in range(i+1, n):
        if event[i] == 1 or event[j] == 1:
          if event[i] == 1 and event[j] == 1:
            permissible += 1.0
                    
            if scores[i] == scores[j]:
              ties += 1.0
            elif y_true[i] < y_true[j] and scores[i] > scores[j]:
              concordant += 1.0
            elif y_true[i] > y_true[j] and scores[i] < scores[j]:
              concordant += 1.0
                
                
                elif event[i] != event[j] :   
                    
                    censored = j
                    uncensored = i
                    
                    if event[i] == 0:
                        censored = i
                        uncensored = j
                        
                    if y_true[uncensored] <= y_true[censored]:
                        permissible += 1.0
                        
                        if scores[uncensored] == scores[censored]:
                             
                            ties += 1.0
                            
                        if scores[uncensored] > scores[censored]:
                            concordant += 1.0
    
     result = (concordant + 0.5*ties) / permissible
     return result

# Train
scores = cph.predict_partial_hazard(one_hot_train)
cox_train_scores = harrell_c(one_hot_train['time'].values, scores.values, one_hot_train['status'].values)
# Validation
scores = cph.predict_partial_hazard(one_hot_val)
cox_val_scores = harrell_c(one_hot_val['time'].values, scores.values, one_hot_val['status'].values)
# Test
scores = cph.predict_partial_hazard(one_hot_test)
cox_test_scores = harrell_c(one_hot_test['time'].values, scores.values, one_hot_test['status'].values)

print("Train:", cox_train_scores)
print("Val:", cox_val_scores)
print("Test:", cox_test_scores)


from rpy2.robjects.packages import importr
base = importr('base')
utils = importr('utils')

import rpy2.robjects.packages as rpackages

forest = rpackages.importr('randomForestSRC', lib_loc='R')

from rpy2 import robjects as ro
R = ro.r

from rpy2.robjects import pandas2ri
pandas2ri.activate()

model = forest.rfsrc(ro.Formula('Surv(time, status) ~ .'), data=df_train, ntree=300, nodedepth=5, seed=-1)
print(model)


result = R.predict(model, newdata=df_val)
scores = np.array(result.rx('predicted')[0])

print("Cox Model Validation Score:", cox_val_scores)
print("Survival Forest Validation Score:", harrell_c(df_val['time'].values, scores, df_val['status'].values))

result = R.predict(model, newdata=df_test)
scores = np.array(result.rx('predicted')[0])

print("Cox Model Test Score:", cox_test_scores)
print("Survival Forest Validation Score:", harrell_c(df_test['time'].values, scores, df_test['status'].values))

vimps = np.array(forest.vimp(model).rx('importance')[0])

y = np.arange(len(vimps))
plt.barh(y, np.abs(vimps))
plt.yticks(y, df_train.drop(['time', 'status'], axis=1).columns)
plt.title("VIMP (absolute value)")
plt.show()

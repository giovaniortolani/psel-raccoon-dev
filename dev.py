'''
Projeto Processo Seletivo - Dev - Raccoon
Autor: Giovani Ortolani Barbosa
'''

import sys
import os
import requests
from statistics import mean
from statistics import pstdev
import time
from datetime import datetime

def getLogs(url, header):
    '''
    Faz uma requisição de logs para a url

    Args:
        url: string com a url do site;
        header: dicionário com as informações do header da requisição (auth token, nesse caso);
    Retorno:
        logs: logs no formato JSON;
    '''

    try:
        r = requests.get(url, headers=header)
        return r.json() 
    except requests.exceptions.RequestException as err:
        print(err)
        sys.exit(1) 

def getTracebacks(logs, lastTBacks):
    '''
    Recupera os últimos 5 tracebacks

    Args:
        logs: logs da requisição atual no formato JSON;
        lastTBacks: lista com os últimos tracebacks das requisições anteriores;
    Retorno:
        lastTBacks: lista atualizada contando os tracebacks da requisição atual;
    '''

    # lista com as últimas tracebacks da última requisição
    localTBacks = []
    # limita a lista de tracebacks a 5 entradas
    numTraceBacks = 5

    # começa a partir do fim da lista de logs, já que estão ordenados por timestamp (aparentemente)
    for log in reversed(logs):
        # somente adiciona na lista de tbacks se for uma tback e se a lista não estiver cheia
        if "traceback" in log and len(localTBacks) < numTraceBacks:
            localTBacks.append(log)
    
    # concatena as novas tbacks com as tbacks de requisições anteriores
    lastTBacks = localTBacks + lastTBacks
    # caso passe do tamanho desejado, elimina as tbacks mais antigas
    if(len(lastTBacks) > numTraceBacks):
        lastTBacks = lastTBacks[:numTraceBacks]

    return lastTBacks 

def calculateStatistics(logs, reqDurList):
    '''
    Calcula a média e desvio-padrão do tempo de resposta das requisições que possuem os
    campos "responde_code" e "request_duration"

    Args:
        logs: logs da requisição atual no formato JSON;
        reqDurList: lista com as durações de todas as requisições passadas;
    Retorno:
        reqDurMean: média do tempo da duração de todas as requisições (passadas + atuais);
        reqDurStdev: desvio-padrão do tempo da duração de todas as requisições (passadas + atuais);
        reqDurList: lista com as durações das requisições passadas + atuais;
    '''

    for log in logs:
        # log é uma requisição
        if "response_code" and "request_duration" in log:
            # armazena na lista de requisições
            reqDurList.append(log["request_duration"])

    # se o request trouxe logs que são requisições, então calcula
    # senão, não faz nada
    if reqDurList:
        reqDurMean = mean(reqDurList)
        reqDurStdev = pstdev(reqDurList)
    else:
        reqDurMean, reqDurStdev = None, None

    return reqDurMean, reqDurStdev, reqDurList
    
def getErrorsStats(logs, errorStats):
    '''
    Calcula o número de mensagens cujo atributo "level" é CRITICAL ou "ERROR", por projeto,
    agrupados por horário

    Args:
        logs: logs da requisição atual no formato JSON;
        errorStats: dicionário cujas chaves são o nome dos projetos e chave possui
                    outro dicionário cujas chaves são os horários;
                    Ex: {
                            'meed_fanager': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}},
                            'dyonisius': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}}
                        }
    Retorno:
        errorStats: mesmo dicionário de entrada, atualizado com os dados do novo request;
    '''

    for log in logs:
        # extrai o horário do timestamp em formato unix epoch time
        hour = time.strftime("%H", time.localtime(log["timestamp"]/1000.))
        # se projeto não está no dict, adiciona ele e o horário
        # senão, verifica se o horário já faz parte do projeto e adiciona caso não faça parte
        if log["project"] not in errorStats:
            errorStats[log["project"]] = {hour: {"ERROR": 0, "CRITICAL": 0}}
        elif hour not in errorStats[log["project"]]:
            errorStats[log["project"]][hour] = {"ERROR": 0, "CRITICAL": 0}

        # incrementa o número de erros ou criticals dependendo do "level" da mensagem
        if log["level"] == "ERROR" or log["level"] == "CRITICAL":
            errorStats[log["project"]][hour][log["level"]] += 1
    
    return errorStats

def printTBacks(lastTBacks):
    '''
    Imprime em formato amigável informações sobre os últimos 5 tracebacks

    Args:
        lastTbacks: lista com os últimos tracebacks das requisições anteriores;
    '''

    i = 1
    print("### Últimos 5 tracebacks ###")
    for log in lastTBacks:
        print("({})".format(i))
        print("Projeto:\n  {}".format(log["project"]))
        print("Mensagem:\n  {}".format(log["message"]))
        print("{}\n".format(log["traceback"]))
        i += 1
    
    if not lastTBacks:
        print("   Sem tracebacks nas últimas requisições\n")

def printStatistics(mean, stdev):
    '''
    Imprime em formato amigável informações sobre a média e desvio-padrão do tempo 
    das requisições

    Args:
        mean: valor da média float;
        stdev: valor do desvio-padrão float;
    '''

    print("### Estatísticas das requisições ###")
    print("  Média:\n    {}".format(mean))
    print("  Desvio padrão:\n    {}".format(stdev))
    print()

def printErrorsStats(errorStats):
    '''
    Imprime em formato amigável informações sobre o número de mensagens com o atributo
    "level" sendo ERROR ou CRITICAL por projeto, agrupados por hora

    Args:
        errorStats: dicionário cujas chaves são o nome dos projetos e chave possui
                    outro dicionário cujas chaves são os horários;
                    Ex: {
                            'meed_fanager': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}},
                            'dyonisius': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}}
                        }
    '''

    print("### Número de ERRORS e CRITICALS por projeto ###")
    for proj, hours in errorStats.items():
        print("  Projeto:\n    {}".format(proj))
        # ordena as chaves do dicionário de horas para poder imprimir em ordem cronológica
        hoursSorted = sorted(hours)
        for hour in hoursSorted:
            print("    ({}h) ERROR: {}, CRITICAL: {}".format(hour, hours[hour]["CRITICAL"], hours[hour]["ERROR"]))

    print()

def run(url, header, lastTBacks, lastReqDurs, errorStats):
    '''
    Faz a requisição dos logs, extrai métricas como tracebacks, estatísticas dos tempos das 
    requisições, número de mensagens de erros e imprime-as

    Args: 
        url: string com a url do site;
        header: dicionário com as informações do header da requisição (auth token, nesse caso);
        lastTbacks: lista com os últimos tracebacks das requisições anteriores;
        lastReqDurs: lista com as durações de todas as requisições passadas;
        errorStats: dicionário cujas chaves são o nome dos projetos e chave possui
                    outro dicionário cujas chaves são os horários;
                    Ex: {
                            'meed_fanager': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}},
                            'dyonisius': {'18': {'CRITICAL': 2, 'ERROR': 0}, '19': {'CRITICAL': 2, 'ERROR': 0}}
                        }
    '''

    logs = getLogs(url, header)
    errorStats = getErrorsStats(logs, errorStats)
    lastTBacks = getTracebacks(logs, lastTBacks)
    mean, stdev, lastReqDurs = calculateStatistics(logs, lastReqDurs)

    print("--------------------------------------------------------------------------------")
    print(datetime.now().strftime("\n%d-%m-%Y %H:%M:%S\n"))
    #_ = os.system('cls' if os.name == 'nt' else 'clear') # limpa a tela
    printErrorsStats(errorStats)
    printTBacks(lastTBacks)
    printStatistics(mean, stdev)
    print("--------------------------------------------------------------------------------")
    
    return lastTBacks, lastReqDurs, errorStats

if __name__ == '__main__':
    # getLogs
    url = "https://psel-logs.raccoon.ag/api/v2/logs"
    header = {"authorization": "2747e5610e9c4262836c5ececc5b5ed4"}
    # getTracebacks
    lastTBacks = []
    # calculateStatistics
    lastReqDurs = []
    # getErrorsStats
    errorStats = {}

    # garante a execução a cada 1 minuto exatamente
    starttime = time.time()
    while True:
        lastTBacks, lastReqDurs, errorStats = run(url, header, lastTBacks, lastReqDurs, errorStats)
        time.sleep(60.0 - ((time.time() - starttime) % 60.0))
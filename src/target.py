# -*- coding: utf-8 -*-
import os

from interpreter import Interpreter, CodeObject, Env
from parser import BytecodeParser
from error import HaneulError
from constant import ConstInteger

from environment import default_globals


def entry_point(argv):
  try:
    filename = argv[1]
  except IndexError:
    print "파일이 필요합니다."
    return 1

  fp = os.open(filename, os.O_RDONLY, 0777)
  content = ""
  while True:
    read = os.read(fp, 4096)
    if len(read) == 0:
      break
    content += read
  os.close(fp)

  parser = BytecodeParser(content)
  (global_var_names, stack_size, local_count,
   const_table, code) = parser.parse_program()

  code_object = CodeObject(const_table, code, local_count, stack_size)
  interpreter = Interpreter(Env(global_var_names, default_globals))
  try:
    interpreter.run(code_object, [])
  except HaneulError as e:
    print (u"%d번째 라인에서 에러 발생 : %s" % (e.error_line, e.message)).encode('utf-8')

  return 0


def target(*args):
  return entry_point, None


def jitpolicy(driver):
  from rpython.jit.codewriter.policy import JitPolicy
  return JitPolicy()

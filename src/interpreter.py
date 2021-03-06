# -*- coding: utf-8 -*-
from rpython.rlib import jit

from instruction import *
from constant import *
from error import HaneulError, InvalidType, ArgNumberMismatch, UnboundVariable, UnboundJosa, UndefinedFunction
from frame import Frame

jitdriver = jit.JitDriver(greens=['pc', 'code_object'],
                          reds=['frame', 'self'],
                          virtualizables=['frame']
                          )


@jit.unroll_safe
def resolve_josa(josa, josa_map):
  if josa == u"_":
    for (j, (k, v)) in enumerate(josa_map):
      if v is None:
        return (k, j)
    raise InvalidType(u"이 함수에는 더 이상 값을 적용할 수 없습니다.")
  else:
    for (j, (k, v)) in enumerate(josa_map):
      if josa == k:
        return (josa, j)
    raise UnboundJosa(u"조사 '%s'를 찾을 수 없습니다." % josa)


def resize_list(l, size, value=None):
  l.extend([value] * (size - len(l)))


class Env:
  def __init__(self, var_map):
    self.var_map = var_map

  def store(self, name, value):
    self.var_map[name] = value

  @jit.elidable
  def lookup(self, name):
    try:
      return self.var_map[name]
    except KeyError:
      raise UnboundVariable(u"변수 '%s'를 찾을 수 없습니다." % name)


class Interpreter:
  def __init__(self, env):
    self.env = env

  def run(self, code_object, args):
    pc = 0
    frame = Frame(code_object.local_number, args, code_object.stack_size)
    code_object = jit.promote(code_object)

    while pc < len(code_object.code):
      jitdriver.jit_merge_point(
          pc=pc, code_object=code_object,
          frame=frame, self=self)

      inst = jit.promote(code_object.code[pc])
      op = jit.promote(inst.opcode)
      try:
        if op == INST_PUSH:
          frame.push(code_object.get_constant(inst.operand_int))

        elif op == INST_POP:
          frame.pop()

        elif op == INST_LOAD_LOCAL:
          frame.push(frame.load(inst.operand_int))

        elif op == INST_STORE_LOCAL:
          # frame.append(frame.pop())
          frame.store(frame.pop(), inst.operand_int)

        elif op == INST_LOAD_DEREF:
          frame.push(code_object.free_vars[inst.operand_int])

        elif op == INST_LOAD_GLOBAL:
          frame.push(self.env.lookup(code_object.var_names[inst.operand_int]))

        elif op == INST_STORE_GLOBAL:
          self.env.store(code_object.var_names[inst.operand_int], frame.pop())

        elif op == INST_CALL:
          given_arity = len(inst.operand_josa_list)

          value = frame.pop()
          if isinstance(value, ConstFunc):
            args = []
            rest_arity = 0

            if value.josa_map is None:
              raise UndefinedFunction(u"선언은 되었으나 정의되지 않은 함수를 호출할 수 없습니다.")

            if len(value.josa_map) == 1 and len(inst.operand_josa_list) == 1 and value.josa_map[0][0] == inst.operand_josa_list[0]:
              args.append(frame.pop())
            else:
              josa_map = list(value.josa_map)
              for josa in inst.operand_josa_list:
                (found_josa, index) = resolve_josa(josa, josa_map)
                josa_map[index] = (found_josa, frame.pop())

              for (_, v) in josa_map:
                args.append(v)
                if v is None:
                  rest_arity += 1

            if rest_arity > 0:
              func = ConstFunc([], value.funcval, value.builtinval)
              func.josa_map = josa_map
              frame.push(func)
            else:  # rest_arity == 0
              if value.builtinval is None:
                result = self.run(value.funcval, args)
                frame.push(result)
              else:
                func_result = value.builtinval(args)
                frame.push(func_result)

          else:
            raise InvalidType(
                u"%s 타입의 값은 호출 가능하지 않습니다." % value.type_name())

        elif op == INST_JMP:
          pc = inst.operand_int
          continue

        elif op == INST_POP_JMP_IF_FALSE:
          value = frame.pop()
          if isinstance(value, ConstBoolean):
            if value.boolval == False:
              pc = inst.operand_int
              continue
          else:
            raise InvalidType(u"여기에는 참 또는 거짓 타입을 필요로 합니다.")

        elif op == INST_FREE_VAR:
          func = frame.pop().copy()

          for (is_free_var, index) in inst.operand_free_var_list:
            if is_free_var:
              value = code_object.free_vars[index]
            else:
              value = frame.load_reserve(index)

            func.funcval.free_vars.append(value)

          frame.push(func)

        elif op == INST_NEGATE:
          value = frame.pop()
          frame.push(value.negate())
        elif op == INST_LOGIC_NOT:
          value = frame.pop()
          frame.push(value.logic_not())
        else:
          rhs, lhs = frame.pop(), frame.pop()
          if op == INST_ADD:
            frame.push(lhs.add(rhs))
          elif op == INST_SUBTRACT:
            frame.push(lhs.subtract(rhs))
          elif op == INST_MULTIPLY:
            frame.push(lhs.multiply(rhs))
          elif op == INST_DIVIDE:
            frame.push(lhs.divide(rhs))
          elif op == INST_MOD:
            frame.push(lhs.mod(rhs))
          elif op == INST_EQUAL:
            frame.push(lhs.equal(rhs))
          elif op == INST_LESS_THAN:
            frame.push(lhs.less_than(rhs))
          elif op == INST_GREATER_THAN:
            frame.push(lhs.greater_than(rhs))
          elif op == INST_LOGIC_AND:
            frame.push(lhs.logic_and(rhs))
          elif op == INST_LOGIC_OR:
            frame.push(lhs.logic_or(rhs))

        pc += 1
      except HaneulError as e:
        if e.error_line == 0:
          e.error_line = inst.line_number
        raise e

    if frame.stack_top == 0:
      return None
    else:
      return frame.pop()

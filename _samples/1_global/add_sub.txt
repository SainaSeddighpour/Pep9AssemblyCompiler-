; value = int(input())
; _UNIV = 42
; result = value + _UNIV
; variable = 3
; result = result - variable
; result = result - 1
; print(result)


BR      Program
_UNIV:      .WORD 42
variable:   .WORD 3
value:      .BLOCK 2  
result:     .BLOCK 2 

Program:    DECI value, d 
            LDWA  _UNIV, d 
            ADDA  value, d
            STWA  result, d
            LDWA  result, d 
            SUBA  variable, d 
            STWA  result, d
            LDWA  result, d
            SUBA  1, i 
            STWA  result, d 
            DECO  result, d 
            .END



def metricify(value):
    val = int(value)
    abs_val = abs(val)
    unit = ''
    sign = ''
    if val >= 0:
        if abs_val >= 10**13:
            unit = 'T'
            abs_val = abs_val // 10**12
        elif abs_val >= 10**10:
            unit = 'G'
            abs_val = abs_val // 10**9
        elif abs_val >= 10**7:
            unit = 'M'
            abs_val = abs_val // 10**6
        elif abs_val >= 10**5:
            unit = 'K'
            abs_val = abs_val // 10**3
    else:
        sign = '-'

        if abs_val >= 10**12:
            unit = 'T'
            if abs_val < 10**13:
                abs_val = '{:.1f}'.format(abs_val// 10**11 / 10).replace(".0", "")
            else:
                abs_val = abs_val // 10**12
        elif abs_val >= 10**9:
            unit = 'G'
            if abs_val < 10**10:
                abs_val = '{:.1f}'.format(abs_val// 10**8 / 10).replace(".0", "")
            else:
                abs_val = abs_val // 10**9
        elif abs_val >= 10**6:
            unit = 'M'
            if abs_val < 10**7:
                abs_val = '{:.1f}'.format(abs_val// 10**5 / 10).replace(".0", "")
            else:
                abs_val = abs_val // 10**6
        elif abs_val >= 10**4:
            unit = 'K'
            abs_val = abs_val // 10**3

    return f'{sign}{abs_val}{unit}'
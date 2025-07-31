def calculate_rax(row):
    rax = 0
    
    # Defensive retrieval with defaults and normalization
    result = str(row.get('result', '')).strip().lower()
    method = str(row.get('method_main', '')).strip().lower()

    # Debug prints to trace values
    print(f"Calculating RAX for: result={result}, method={method}")

    # RAX for wins
    if result == 'win':
        if 'ko/tko' in method:
            rax += 100
        elif 'submission' in method:
            rax += 90
        elif 'decision - unanimous' in method:
            rax += 80
        elif 'decision - majority' in method:
            rax += 75
        elif 'decision - split' in method:
            rax += 70
        else:
            rax += 60  # fallback for other win methods
    elif result == 'loss':
        rax += 25

    # Defensive conversion to int for strikes (handle missing or invalid)
    try:
        sig_str_fighter = int(float(row.get('TOT_fighter_SigStr_landed', 0)))
    except (ValueError, TypeError):
        sig_str_fighter = 0

    try:
        sig_str_opponent = int(float(row.get('TOT_opponent_SigStr_landed', 0)))
    except (ValueError, TypeError):
        sig_str_opponent = 0

    # Debug print strikes
    # print(f"Strikes landed - Fighter: {sig_str_fighter}, Opponent: {sig_str_opponent}")

    # Strike difference bonus
    if sig_str_fighter > sig_str_opponent:
        rax += (sig_str_fighter - sig_str_opponent)

    # 5-round fight bonus
    time_format = str(row.get('TimeFormat', '')).lower()
    if '5 rnd' in time_format:
        rax += 25

    # Fight of the night bonus
    details_text = str(row.get('Details', '')).lower()
    if 'fight of the night' in details_text:
        rax += 50

    return rax

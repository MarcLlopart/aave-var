SELECT
    borrower,
    symbol, 
    token_address, 
    sum(amount_usd) as total_borrowed_amt
FROM aave_ethereum.borrow
WHERE blockchain = 'ethereum'
    and version = '3'
GROUP BY borrower, symbol,token_address
HAVING sum(amount) > 0 
ORDER by total_borrowed_amt DESC
LIMIT 1000